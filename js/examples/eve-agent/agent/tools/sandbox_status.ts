import { defineTool } from "eve/tools";
import { z } from "zod";

export default defineTool({
  description: "Inspect the current Lightning sandbox and its persistent workspace.",
  inputSchema: z.object({}),
  async execute(_input, ctx) {
    const sandbox = await ctx.getSandbox();
    const result = await sandbox.run({
      command: "printf 'cwd='; pwd; printf 'kernel='; uname -sr; printf 'files='; find . -maxdepth 1 -mindepth 1 -printf '%f\\n' | sort",
    });

    return {
      sandboxId: sandbox.id,
      workspace: sandbox.resolvePath("."),
      exitCode: result.exitCode,
      output: result.stdout,
    };
  },
});
