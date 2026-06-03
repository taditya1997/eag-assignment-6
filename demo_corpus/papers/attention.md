# Attention Is All You Need - Session 7 Demo Notes

The Transformer architecture replaces recurrent sequence processing with an
attention-only encoder-decoder design. Its first major contribution is scaled
dot-product self-attention, where every token can compare itself with every
other token in a sequence and form context-aware representations. This gives the
model a direct path between distant words instead of forcing information through
many recurrent steps.

The second contribution is multi-head attention. Rather than computing one
attention pattern, the model computes several attention heads in parallel. Each
head can focus on a different relation, such as local syntax, long-range
dependency, alignment between source and target, or phrase-level grouping. The
outputs are concatenated and projected into the next representation.

The third contribution is parallel sequence computation. Because the model does
not process tokens one at a time through recurrence, training can run across all
positions in a sentence at once. This improves hardware utilization and makes it
practical to train on larger corpora. The architecture uses positional encodings
to preserve order information that recurrence would otherwise provide.

The paper also demonstrates that an attention-only model can achieve strong
translation quality while being faster to train than recurrent or convolutional
alternatives. The encoder layers combine multi-head self-attention with
position-wise feed-forward networks. The decoder adds masked self-attention and
encoder-decoder attention so generation can condition on previous target tokens
and the source sentence.
