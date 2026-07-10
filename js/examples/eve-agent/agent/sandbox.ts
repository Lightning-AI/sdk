import { defineSandbox } from "eve/sandbox";
import { lightningSandbox } from "../lib/lightning-sandbox.js";

export default defineSandbox({
  description: "A durable Lightning AI CPU sandbox with a persistent /workspace.",
  backend: lightningSandbox({
    instanceType: "cpu-1",
    networkPolicy: "allow-all",
    timeout: 30 * 60_000,
  }),
});
