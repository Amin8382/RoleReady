# Future supervised-learning data

No fine-tuning data or training run is introduced by Mission 003.

This is a distinct, ignored destination for future reviewed, licensed instruction
examples and their train/validation/test partitions. Keep CV/job-conditioned
examples separate from general interview Q&A. Establish grouping, duplicate and
leakage policies before exporting training data; never use retrieval evaluation
queries, benchmark C, or generation-evaluation scenarios as SFT examples.

The versioned retrieval corpus at `../mission003/processed/corpus.jsonl` is a
searchable knowledge collection, not a training split. Its records explicitly
reject the legacy SFT loader. Existing `roleready_ai.datasets` splitting and
`roleready_ai.sft` reviewed-TRAIN export remain supported for legacy banks.

Keep future candidate content private. Approval of a publisher's dataset license
does not approve technical answers, reference criteria or candidate consent.
