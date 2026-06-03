# LoRA - Session 7 Demo Notes

LoRA, or Low-Rank Adaptation, is a parameter-efficient method for adapting large
neural networks. Instead of updating all weights in a pretrained model, it freezes
the original weights and learns small low-rank matrices that are inserted into
selected layers. During inference, the low-rank update can be merged with the
base weights or applied as an adapter.

The main contribution is efficiency. Fine-tuning a large model normally requires
storing optimizer state and gradients for billions of parameters. LoRA trains a
much smaller set of parameters while preserving much of the quality of full
fine-tuning. This reduces memory cost, storage cost, and the operational burden
of serving many task-specific variants.

The method also offers a way to distribute behavioral change through a compact
set of trainable directions. A small adapter can influence attention and feed
forward layers without rewriting the whole model. In multi-step reasoning
systems, that means a narrow set of learned parameters can alter how information
flows through later layers and how partial cues affect the final output.

LoRA is useful in RAG settings when a team wants the base model to keep its
general language ability but adapt to a domain-specific style, citation policy,
or document-grounded answer format.
