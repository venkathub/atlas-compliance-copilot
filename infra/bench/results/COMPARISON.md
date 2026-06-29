### Throughput — output tokens/sec by concurrency

| Concurrency | ollama | vllm |
|---|---|---|
| 1 | 47.8 | 53.1 |
| 4 | 51.1 | 193.4 |
| 8 | 51.1 | 359.1 |
| 16 | 51.0 | 682.1 |
| 32 | 50.9 | 1207.8 |

### Latency p99 (end-to-end, ms) by concurrency

| Concurrency | ollama | vllm |
|---|---|---|
| 1 | 2690 | 2418 |
| 4 | 8803 | 2524 |
| 8 | 18664 | 2511 |
| 16 | 36112 | 2652 |
| 32 | 69213 | 2966 |

### Peak throughput & measured cost

| Backend | Model | Peak tok/s | @concurrency | Cost / 1M tok | Token acct |
|---|---|---|---|---|---|
| ollama | qwen2.5:7b-instruct | 51.1 | 4 | 224.3402 | server-reported |
| vllm | Qwen/Qwen2.5-7B-Instruct-AWQ | 1207.8 | 32 | 9.5004 | server-reported |

> **Peak throughput ratio (vllm / ollama): 23.61×** (same GPU, same model family). See notes for quantization caveats.
