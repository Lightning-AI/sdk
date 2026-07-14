/**
 * Graph nodes: the actions that mutate the agent's state.
 *
 * Each node takes the current state and returns a *partial* update (only the
 * channels it changes) — the idiomatic LangGraph.js pattern. The LLM-backed
 * nodes (`generate` and `evaluateExecution`) are built as standard LangChain
 * LCEL chains -- `PromptTemplate | chatModel.withStructuredOutput(Schema)` --
 * so the model returns validated objects directly. The chat model is the stock
 * `ChatOpenAI` integration pointed at Lightning's gateway (see `llm.ts`).
 */
import { PromptTemplate } from "@langchain/core/prompts";
import type { Runnable } from "@langchain/core/runnables";
import { z } from "zod";
import type { Sandbox } from "@lightningai/sdk";
import {
  DEBUG_MODEL,
  MODEL,
  type GraphStateType,
  type GraphUpdate,
} from "./common.js";
import { makeChatModel } from "./llm.js";

/** A structured code solution the agent generates and then executes. */
export const CodeSchema = z.object({
  prefix: z.string().describe("Description of the problem and approach"),
  imports: z.string().describe("Code block import statements"),
  code: z.string().describe("Code block not including import statements"),
});

export type Code = z.infer<typeof CodeSchema>;

/** The evaluator's verdict on a code execution result. */
export const ExecutionEvaluationSchema = z.object({
  decision: z.enum(["finish", "retry"]).describe("Decision to finish or retry"),
  explanation: z.string().describe("Explanation for the decision"),
});

export type ExecutionEvaluation = z.infer<typeof ExecutionEvaluationSchema>;

/** Result of executing code in the sandbox: [exitCode, stdout, stderr]. */
export type RunFn = (code: string, sb: Sandbox) => Promise<[number, string, string]>;

const GENERATE_TEMPLATE = `
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
{question}`;

const RETRY_ADDENDUM = `
You previously tried to solve this problem. Here is your solution:

{generation}

Here is the resulting error from code execution:

{error}

Please re-try to answer this. Structure your answer with a description of the code solution.
Then list the imports. And finally list the functioning code block.`;

const EVALUATE_TEMPLATE = `You are an expert code evaluator. Analyze the following code execution results and determine if the execution was successful.

Code:
{code}

Output:
{output}

Error:
{error}

Decide whether to finish (if the execution was successful) or retry (if there were errors or unexpected results).
Provide a brief explanation for your decision.`;

export class Nodes {
  private readonly context: string;
  private readonly debug: boolean;
  private readonly model: string;
  private readonly codeChainModel: Runnable<any, Code>;
  private readonly evalChain: Runnable<any, ExecutionEvaluation>;
  private readonly sb: Sandbox;
  private readonly run: RunFn;

  constructor(
    context: string,
    sb: Sandbox,
    run: RunFn,
    { debug = false, apiKey }: { debug?: boolean; apiKey?: string } = {},
  ) {
    this.context = context;
    this.debug = debug;
    this.model = this.debug ? DEBUG_MODEL : MODEL;

    // A single LangChain chat model drives both LLM nodes. `withStructuredOutput`
    // (via function calling) makes the model return validated objects.
    const chatModel = makeChatModel(this.model, { apiKey });
    this.codeChainModel = chatModel.withStructuredOutput(CodeSchema, {
      name: "Code",
      method: "functionCalling",
    });
    this.evalChain = PromptTemplate.fromTemplate(EVALUATE_TEMPLATE).pipe(
      chatModel.withStructuredOutput(ExecutionEvaluationSchema, {
        name: "ExecutionEvaluation",
        method: "functionCalling",
      }),
    );

    this.sb = sb;
    this.run = run;

    // Bind so the methods can be passed as bare references to `addNode`.
    this.generate = this.generate.bind(this);
    this.checkCodeImports = this.checkCodeImports.bind(this);
    this.checkCodeExecution = this.checkCodeExecution.bind(this);
    this.evaluateExecution = this.evaluateExecution.bind(this);
    this.finish = this.finish.bind(this);
  }

  /** Generate a code solution from the docs + question (with error feedback on retries). */
  async generate(state: GraphStateType): Promise<GraphUpdate> {
    // `error` is unset on the first attempt and present on every retry.
    const isRetry = state.error !== undefined;

    let generation: Code;
    if (isRetry) {
      console.log("---RE-GENERATE SOLUTION w/ ERROR FEEDBACK---");
      const prompt = PromptTemplate.fromTemplate(GENERATE_TEMPLATE + RETRY_ADDENDUM);
      generation = await prompt.pipe(this.codeChainModel).invoke({
        context: this.context,
        question: state.question,
        generation: JSON.stringify(state.generation),
        error: state.error,
      });
    } else {
      console.log("---GENERATE SOLUTION---");
      const prompt = PromptTemplate.fromTemplate(GENERATE_TEMPLATE);
      generation = await prompt.pipe(this.codeChainModel).invoke({
        context: this.context,
        question: state.question,
      });
    }

    return { generation, iterations: state.iterations + 1 };
  }

  /** Run just the imports in the sandbox; a non-zero exit code marks a failure. */
  async checkCodeImports(state: GraphStateType): Promise<GraphUpdate> {
    console.log("---CHECKING CODE IMPORTS---");
    const imports = state.generation!.imports;

    // Only a non-zero exit code counts as a failure; imports can emit benign
    // warnings to stderr while still succeeding.
    const [returncode, output, err] = await this.run(imports, this.sb);
    let error: string;
    if (returncode !== 0) {
      console.log("---CODE IMPORT CHECK: FAILED---");
      error = `Execution error: ${err}`;
      console.error(`Error: ${error}`);
      if (state.error !== undefined) {
        error = `
${state.error}

--- Most recent run output and error ---
------ output ------
${output}
------ error ------
${error}
`;
      }
    } else {
      console.log("---CODE IMPORT CHECK: SUCCESS---");
      error = "None";
    }

    return { error };
  }

  /** Run the full import + code block in the sandbox; capture output/error. */
  async checkCodeExecution(state: GraphStateType): Promise<GraphUpdate> {
    console.log("---CHECKING CODE EXECUTION---");
    const { imports, code } = state.generation!;
    const codeBlock = imports + "\n" + code;

    // As above, only a non-zero exit code counts as a failure; stderr may just
    // carry warnings (e.g. Hugging Face download progress).
    const [returncode, output, err] = await this.run(codeBlock, this.sb);
    let error: string;
    if (returncode !== 0) {
      console.log("---CODE BLOCK CHECK: FAILED---");
      error = `Execution error: ${err}`;
      console.error(`Error: ${error}`);
      if (state.error !== undefined) {
        error =
          state.error +
          "\n --- Most recent run output and error --- \n" +
          " ------ output ------ \n" +
          output +
          "\n ------ error ------ \n" +
          error;
      }
    } else {
      console.log("---CODE BLOCK CHECK: SUCCESS---");
      error = "None";
    }

    return { error, output };
  }

  /** Ask the LLM to judge the execution result and decide finish vs. retry. */
  async evaluateExecution(state: GraphStateType): Promise<GraphUpdate> {
    console.log("---EVALUATING EXECUTION---");

    const evaluation = await this.evalChain.invoke({
      code: state.generation!.code,
      output: state.output,
      error: state.error,
    });

    return { evaluation };
  }

  /** Assemble the final response and delete the sandbox. */
  async finish(state: GraphStateType): Promise<GraphUpdate> {
    console.log("---FINISHING---");
    const response = extractResponse(state);
    await this.sb.delete();
    return { response };
  }
}

/** Render the final answer: the approach, the code, and its real execution output. */
export function extractResponse(state: GraphStateType): string {
  const { prefix, imports, code } = state.generation!;
  const codeOutput = state.output;

  return `${prefix}

${imports}
${code}

Result of code execution:
${codeOutput}
`;
}
