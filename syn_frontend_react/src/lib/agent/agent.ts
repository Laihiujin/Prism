import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { MemorySaver } from "@langchain/langgraph/web";
import { ChatOpenAI } from "@langchain/openai";
import { tools } from "./tools";

const PROMPT = `
你是 Synapse Automation 的 AI 助手，代号“小轴”。
你可以用 emoji 表达情绪，喜欢用表格展示数据。
你可以使用工具来：
1) 列出可运行的脚本
2) 按需执行 syn_backend/scripts 下的脚本

在建议执行脚本前，解释原因与预期效果，避免危险操作。
不要使用图片，尽量返回表格或要点列表。
`;

interface AgentConfig {
  apiKey?: string;
  baseURL?: string;
  model?: string;
}

function createAgent(config: AgentConfig) {
  const agentModel = new ChatOpenAI({
    apiKey: config.apiKey,
    configuration: {
      baseURL: config.baseURL,
    },
    model: config.model,
  });

  const agentModelWithTools = agentModel.bindTools(tools, {
    parallel_tool_calls: false,
  });

  const agentCheckpointer = new MemorySaver();
  const agent = createReactAgent({
    llm: agentModelWithTools,
    checkpointSaver: agentCheckpointer,
    interruptBefore: ["tools"],
    prompt: PROMPT,
    tools,
  });

  return agent;
}

export default createAgent;

