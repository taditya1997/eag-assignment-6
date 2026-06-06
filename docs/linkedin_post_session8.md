# LinkedIn Draft

🚀 Built a DAG-based agent orchestrator for my EAG Session 8 assignment!

This project turns the earlier single-loop agent into a graph executor where:

🔀 Planner emits a DAG of skill nodes  
⚡ Executor runs independent branches concurrently with `asyncio.gather`  
🧪 Critic checks verifiable outputs and splices in recovery when a run fails  
🐍 Coder emits Python that the SandboxExecutor runs for exact computation  
🧩 New skills are YAML entries plus prompt files, without changing the orchestrator  

Demo highlights:

✅ Passed the base queries: hello, Shannon, city populations, graceful failure, and resume  
✅ Proved fan-out wall-clock is max(branches), not sum(branches)  
✅ Showed Critic pass and fail/recovery runs  
✅ Added a new `tabulator` skill through `agent_config.yaml`  

🔗 GitHub: https://github.com/taditya1997/eag-assignment-6

Built as part of the EAG program.

#AIAgents #DAG #MCP #RAG #LLMOps #BuildInPublic #EngineeringAI

Note: only post/share for the assignment if your LinkedIn account has more than 50 followers.
