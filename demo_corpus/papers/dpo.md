# Direct Preference Optimization - Session 7 Demo Notes

Direct Preference Optimization studies how to align a language model with human
preferences without running a separate reinforcement-learning stage. The method
uses pairs of outputs where one response is preferred over another. It optimizes
the policy directly so the preferred response becomes more likely and the
rejected response becomes less likely.

The central contribution is a stable objective that connects preference data to
policy updates. Instead of training a reward model and then optimizing against
that learned reward, DPO derives a supervised loss from the preference pair and a
reference model. This makes the training pipeline simpler and easier to
reproduce.

For multi-step behavior, preference pairs can shape which parts of a response
trajectory are reinforced. If the chosen answer contains better reasoning,
safer refusal behavior, or a more faithful citation pattern, the optimization
nudges the model toward those traits. The final label is pairwise, but the
language sequence contains many intermediate choices that become more or less
likely through the update.

DPO is therefore relevant to retrieval systems because preference data can favor
answers that use evidence well, avoid unsupported claims, and synthesize sources
without over-copying them. It is not a retriever, but it can teach the generator
how to use retrieved chunks responsibly.
