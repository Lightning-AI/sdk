/** Conditional-edge routers that transition our agent from one node to another. */
import type { GraphStateType } from "./common.js";

/** Determines whether to test code execution, or re-try answer generation. */
export function decideToCheckCodeExec(
  state: GraphStateType,
): "checkCodeExecution" | "generate" {
  console.log("---DECIDE TO TEST CODE EXECUTION---");

  if (state.error === "None") {
    // Imports ran cleanly -- go execute the full code block.
    console.log("---DECISION: TEST CODE EXECUTION---");
    return "checkCodeExecution";
  }
  // Imports failed -- regenerate the solution with the error as feedback.
  console.log("---DECISION: RE-TRY SOLUTION---");
  return "generate";
}

/** Determines whether to finish (re-try code up to 3 times). */
export function decideToFinish(
  state: GraphStateType,
): "finish" | "generate" {
  console.log("---DECIDE TO FINISH---");

  if (state.evaluation?.decision === "finish" || state.iterations >= 3) {
    console.log("---DECISION: FINISH---");
    return "finish";
  }
  console.log("---DECISION: RE-TRY SOLUTION---");
  return "generate";
}
