"""Graph nodes: the actions that mutate the agent's state.

Each node is a plain function ``GraphState -> GraphState``. The LLM-backed nodes
(``generate`` and ``evaluate_execution``) are built as standard LangChain LCEL
chains -- ``PromptTemplate | chat_model.with_structured_output(Schema)`` -- so
the model returns validated Pydantic objects directly. The chat model is the
stock ``ChatOpenAI`` integration pointed at Lightning's gateway (see ``llm.py``).
"""

import sys
from enum import Enum
from operator import itemgetter
from typing import Callable, Optional

from langchain_core.prompts import PromptTemplate
from lightning_sdk.sandbox import SandboxInstance
from pydantic import BaseModel, Field

from .common import DEBUG_MODEL, MODEL, GraphState
from .llm import make_chat_model


class Code(BaseModel):
    """A structured code solution the agent generates and then executes."""

    prefix: str = Field(description="Description of the problem and approach")
    imports: str = Field(description="Code block import statements")
    code: str = Field(description="Code block not including import statements")


class Decision(str, Enum):
    FINISH = "finish"
    RETRY = "retry"


class ExecutionEvaluation(BaseModel):
    """The evaluator's verdict on a code execution result."""

    decision: Decision = Field(description="Decision to finish or retry")
    explanation: str = Field(description="Explanation for the decision")


GENERATE_TEMPLATE = """
You are a coding assistant with expertise in Python.
You are able to execute Python code in a sandbox environment.
You are tasked with responding to the following user question: {question}
Your response will be shown to the user.
Here is a full set of documentation:

-------
{context}
-------

Answer the user question based on the above provided documentation.
Ensure any code you provide can be executed with all required imports and variables defined.
Structure your answer as a description of the code solution,
then a list of the imports, and then finally list the functioning code block.
Here is the user question again:

--- --- ---
{question}"""

RETRY_ADDENDUM = """
You previously tried to solve this problem. Here is your solution:

{generation}

Here is the resulting error from code execution:

{error}

Please re-try to answer this. Structure your answer with a description of the code solution.
Then list the imports. And finally list the functioning code block."""

EVALUATE_TEMPLATE = """
You are an expert code evaluator. Analyze the following code execution results and determine if the execution was successful.

Code:
{code}

Output:
{output}

Error:
{error}

Decide whether to finish (if the execution was successful) or retry (if there were errors or unexpected results).
Provide a brief explanation for your decision.
""".strip()


class Nodes:
    def __init__(
        self,
        context: str,
        sb: SandboxInstance,
        run: Callable[[str, SandboxInstance], tuple[int, str, str]],
        debug: bool = False,
        api_key: Optional[str] = None,
    ):
        self.context = context
        self.debug = debug
        self.model = MODEL if not self.debug else DEBUG_MODEL

        # A single LangChain chat model drives both LLM nodes. ``with_structured_output``
        # (via function calling) makes the model return validated Pydantic objects.
        chat_model = make_chat_model(self.model, api_key=api_key)
        self.code_chain_model = chat_model.with_structured_output(
            Code, method="function_calling"
        )
        self.eval_chain = (
            PromptTemplate.from_template(EVALUATE_TEMPLATE)
            | chat_model.with_structured_output(
                ExecutionEvaluation, method="function_calling"
            )
        )

        self.node_map = {
            "generate": self.generate,
            "check_code_imports": self.check_code_imports,
            "check_code_execution": self.check_code_execution,
            "evaluate_execution": self.evaluate_execution,
            "finish": self.finish,
        }

        self.sb = sb
        self.run = run

    def generate(self, state: GraphState) -> GraphState:
        """Generate a code solution from the docs + question (with error feedback on retries)."""
        state_dict = state["keys"]
        question = state_dict["question"]
        iterations = state_dict["iterations"]

        if "error" in state_dict:
            print("---RE-GENERATE SOLUTION w/ ERROR FEEDBACK---")
            prompt = PromptTemplate.from_template(GENERATE_TEMPLATE + RETRY_ADDENDUM)
            chain = (
                {
                    "context": lambda _: self.context,
                    "question": itemgetter("question"),
                    "generation": itemgetter("generation"),
                    "error": itemgetter("error"),
                }
                | prompt
                | self.code_chain_model
            )
            code_solution = chain.invoke(
                {
                    "question": question,
                    "generation": str(state_dict["generation"][0]),
                    "error": state_dict["error"],
                }
            )
        else:
            print("---GENERATE SOLUTION---")
            prompt = PromptTemplate.from_template(GENERATE_TEMPLATE)
            chain = (
                {
                    "context": lambda _: self.context,
                    "question": itemgetter("question"),
                }
                | prompt
                | self.code_chain_model
            )
            code_solution = chain.invoke({"question": question})

        return {
            "keys": {
                "generation": [code_solution],
                "question": question,
                "iterations": iterations + 1,
            }
        }

    def check_code_imports(self, state: GraphState) -> GraphState:
        """Run just the imports in the sandbox; a non-zero exit code marks a failure."""
        print("---CHECKING CODE IMPORTS---")
        state_dict = state["keys"]
        question = state_dict["question"]
        code_solution = state_dict["generation"]
        imports = code_solution[0].imports
        iterations = state_dict["iterations"]

        # Only a non-zero exit code counts as a failure; imports can emit benign
        # warnings to stderr while still succeeding.
        returncode, output, error = self.run(imports, self.sb)
        if returncode != 0:
            print("---CODE IMPORT CHECK: FAILED---")
            error = f"Execution error: {error}"
            print(f"Error: {error}", file=sys.stderr)
            if "error" in state_dict:
                error = f"""
{state_dict["error"]}

--- Most recent run output and error ---
------ output ------
{output}
------ error ------
{error}
"""
        else:
            print("---CODE IMPORT CHECK: SUCCESS---")
            error = "None"

        return {
            "keys": {
                "generation": code_solution,
                "question": question,
                "error": error,
                "iterations": iterations,
            }
        }

    def check_code_execution(self, state: GraphState) -> GraphState:
        """Run the full import + code block in the sandbox; capture output/error."""
        print("---CHECKING CODE EXECUTION---")
        state_dict = state["keys"]
        question = state_dict["question"]
        code_solution = state_dict["generation"]
        imports = code_solution[0].imports
        code = code_solution[0].code
        code_block = imports + "\n" + code
        iterations = state_dict["iterations"]

        # As above, only a non-zero exit code counts as a failure; stderr may
        # just carry warnings (e.g. Hugging Face download progress).
        returncode, output, error = self.run(code_block, self.sb)
        if returncode != 0:
            print("---CODE BLOCK CHECK: FAILED---")
            error = f"Execution error: {error}"
            print(f"Error: {error}", file=sys.stderr)
            if "error" in state_dict:
                error = (
                    state_dict["error"]
                    + "\n --- Most recent run output and error --- \n"
                    " ------ output ------ \n"
                    + output
                    + "\n ------ error ------ \n"
                    + error
                )
        else:
            print("---CODE BLOCK CHECK: SUCCESS---")
            error = "None"

        return {
            "keys": {
                "generation": code_solution,
                "question": question,
                "error": error,
                "output": output,
                "iterations": iterations,
            }
        }

    def evaluate_execution(self, state: GraphState) -> GraphState:
        """Ask the LLM to judge the execution result and decide finish vs. retry."""
        print("---EVALUATING EXECUTION---")
        state_dict = state["keys"]
        code_solution = state_dict["generation"][0]

        evaluation = self.eval_chain.invoke(
            {
                "code": code_solution.code,
                "output": state_dict["output"],
                "error": state_dict["error"],
            }
        )

        return {"keys": {**state_dict, "evaluation": evaluation}}

    def finish(self, state: GraphState) -> dict:
        """Assemble the final response and delete the sandbox."""
        print("---FINISHING---")
        response = extract_response(state)
        self.sb.delete()
        return {"keys": {"response": response}}


def extract_response(state: GraphState) -> str:
    """Render the final answer: the approach, the code, and its real execution output."""
    state_dict = state["keys"]
    code_solution = state_dict["generation"][0]

    prefix = code_solution.prefix
    imports = code_solution.imports
    code = code_solution.code
    code_output = state_dict["output"]

    return f"""{prefix}

{imports}
{code}

Result of code execution:
{code_output}
"""
