# ReAct - Session 7 Demo Notes

ReAct combines reasoning traces with actions. Instead of producing a purely
linear explanation and then an answer, the model alternates between thoughts and
tool or environment actions. A thought decides what information is needed or what
hypothesis should be checked. An action queries a source, searches a page, calls
a tool, or manipulates an environment. The observation from that action becomes
part of the next reasoning step.

This interleaving changes the role of intermediate reasoning. The text is not
only a private scratchpad; it is also a controller for information gathering. If
the model is uncertain, it can search. If a plan fails, it can revise after
seeing the observation. ReAct is therefore useful for tasks where factual
knowledge, navigation, or external state matters.

The paper shows that the combination improves interpretability and robustness.
Reasoning steps explain why an action was taken, while observations ground the
next step in external evidence. The model receives intermediate signals from the
environment after each action, so success can be shaped by which step gathered
the decisive evidence and which step led the agent away from an error.

Compared with purely written reasoning, ReAct is less linear. It is a loop:
think, act, observe, then think again. That loop is the architectural distinction
that matters for retrieval-aware agents.
