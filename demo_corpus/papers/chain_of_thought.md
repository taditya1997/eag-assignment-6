# Chain-of-Thought Reasoning - Session 7 Demo Notes

Chain-of-thought prompting studies how large language models improve on tasks
that require multiple reasoning steps when they are encouraged to write
intermediate rationales before the final answer. The key idea is that a model can
externalize a sequence of small inferences, arithmetic subresults, or symbolic
transformations, then use those written steps as context for later steps.

The paper treats intermediate reasoning as a linear trace. A prompt contains a
few examples where the answer is preceded by a natural-language explanation.
During inference, the model follows that pattern and produces a stepwise
solution. This is especially helpful for arithmetic word problems, commonsense
multi-hop questions, and symbolic manipulation tasks.

The mechanism does not use tools or environmental feedback. It relies on the
model's internal knowledge and the additional tokens in the rationale. When a
long solution succeeds, earlier steps act as working memory for later steps. If a
step is wrong, the remaining trace can amplify the error, so the approach
benefits from sampling multiple traces and selecting consistent answers.

For multi-step learning, the important signal is distributed across the written
trace: the final answer is not the only useful token. Training or prompting can
reward traces that preserve useful partial results, expose assumptions, and make
later verification easier. The paper therefore frames intermediate text as a
scaffold for solving tasks that are difficult to answer in a single jump.
