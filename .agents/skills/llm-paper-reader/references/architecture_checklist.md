# Architecture Checklist

Use this checklist when the paper proposes or modifies a model, training framework, inference system, agent, RAG pipeline, or multimodal architecture.

## Model Surface

- Task input and output format
- Closest familiar architecture or conventional baseline for the default reader
- Prerequisite concepts the paper assumes but does not explain
- Tokenization or representation assumptions
- Base model, backbone, encoder, decoder, or pretrained checkpoint
- Whether the method changes architecture, training, inference, or only data

## Transformer and LLM Internals

- Embedding changes
- Transformer block changes
- Attention mechanism
- KV cache, memory, recurrence, or context extension
- MLP or feed-forward changes
- Normalization and residual path changes
- Positional encoding or relative position handling
- MoE experts, router, adapter, LoRA, prompt, prefix, or soft-token mechanisms

## External Interfaces

- Retrieval index, memory store, database, tools, APIs, simulator, or planner
- Vision, audio, video, code, graph, or other modality encoders
- Cross-attention, projection, connector, resampler, perceiver, or fusion layer
- Data construction or filtering pipeline

## Training and Inference

- Training stages and their order
- Objective functions and losses
- Teacher, reward model, preference model, verifier, critic, or generator roles
- Sampling, decoding, reranking, search, self-consistency, or tool-use policy
- Differences between training-time and inference-time behavior

## Module Call Graph

For every paper-specific module or important function:

- caller and call site
- purpose
- inputs and shapes
- internal operations in order
- masks, routing, retrieval, or sampling rules
- outputs and shapes
- trainable/frozen/cached/external state
- gradient or update path

Do not stop at an end-to-end flow if a central module remains an unexplained black box.

## Cost and Constraints

- Parameter count
- FLOPs, latency, memory, context length, throughput, or serving cost
- Hardware assumptions
- Scaling behavior
- Failure modes caused by cost or context limits

## Required Output

For every important component, record:

- name used in the paper
- conventional predecessor or familiar starting point
- prerequisite bridge required by the default reader
- function
- input
- output
- connection to other components
- evidence anchor
- whether the connection is explicit or inferred from the paper
- exact operational difference from the closest baseline
