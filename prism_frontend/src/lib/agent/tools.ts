import { tool } from "@langchain/core/tools";
import { z } from "zod";
import { invoke } from "./invoker";

// List runnable backend scripts
const list_scripts = tool(
  async () => {
    const result = await invoke("list_scripts");
    return result;
  },
  {
    name: "list_scripts",
    description: "List available automation scripts on the backend",
    schema: z.object({}),
  }
);

// Run a backend script (potentially sensitive)
const run_script = tool(
  async (input: any) => {
    const result = await invoke("run_script", input);
    return result;
  },
  {
    name: "run_script",
    description:
      "Run a backend automation script by filename with optional arguments",
    schema: z.object({
      name: z.string().describe("The script filename inside syn_backend/scripts"),
      args: z
        .array(z.string())
        .optional()
        .describe("Optional arguments passed to the script"),
    }),
  }
);

export const tools = [list_scripts, run_script];

