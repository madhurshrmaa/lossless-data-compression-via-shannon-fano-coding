# CS 3358 Honors Credit — Project 5B: Lossless Data Compression via Shannon-Fano Coding

**Author:** Madhur Sharma  
**Course:** CS 3358: Data Structures & Algorithms (Fall 2026)  
**Faculty Supervisor:** Dr. Suddhasvatta Das  
**AI Chat Logs:** [Google Docs — AI Chat Logs](https://docs.google.com/document/d/1kYjS5IgYyAm4EPcFUPwKFhI1cOfFmFRtc6RMbePV5u4/edit?usp=sharing)

---

## Overview

This repository implements an end-to-end lossless statistical data compression and decompression pipeline in pure Python using **Shannon-Fano coding** (top-down recursive bipartitioning), benchmarked against an in-memory **Huffman coding** baseline and theoretical **Shannon entropy $H(X)$**.

### Core Capabilities
1. **Frequency Analysis & Deterministic Sorting (`build_frequency_table`):**  
   Scans input text of length $N$ in $O(N)$ time via `collections.Counter` and sorts $U = |\Sigma|$ unique symbols in $O(U \log U)$ time using `(-freq, ord(char))` so ties break deterministically by ascending Unicode/ASCII code point.
2. **Prefix-Sum Accelerated Top-Down Partitioning (`build_shannon_fano_codes`):**  
   Builds a 0-based 1D prefix-sum array in $O(U)$ time so each candidate split imbalance $\Delta(k) = |\text{left\_sum} - \text{right\_sum}|$ is evaluated in $O(1)$ time, with unimodal early exit and strict `<` tie-breaking (selecting the earlier split position $k$).
3. **Self-Describing Binary Framing & Lossless Decoding (`encode_to_bytes`, `decode_from_bytes`):**  
   Serializes a compact big-endian `SF5B` binary header ($14 + 6U$ bytes storing magic tag `SF5B`, original character count $N$, exact unpadded bit length `total_bits`, symbol count $U$, and the frequency table) followed by the byte-aligned bitstream. The decoder reconstructs the exact trie, strips trailing zero-padding bits, and halts at $N$ characters.
4. **In-Memory Huffman Baseline (`build_huffman_codes`):**  
   Constructs an optimal prefix-free tree via `heapq` in $O(U \log U)$ time for direct bit-length and tree-depth comparison ($L_{\text{Huff}} \le L_{\text{SF}}$).

---

## Repository Contents

| File | Description |
| :--- | :--- |
| `project_5b_shannon_fano.py` | Complete Shannon-Fano encoder/decoder, Huffman baseline, and 22-dataset benchmark harness |
| `benchmark_results_v2.json` | Reproducible JSON output from all 4 experimental suites (`seed = 3358`) |
| `CS3358_Project_5B_Final_Report_Madhur_Sharma.docx` | Final honors credit technical report with pseudocode, tables, and empirical plots |

---

## Quick Start

Requires **Python 3.10+** using only the Python standard library (no external dependencies).

```bash
python project_5b_shannon_fano.py
```

Running the script executes all 22 controlled and edge-case datasets, verifies `decode_from_bytes(encode_to_bytes(T)) == T`, checks Kraft's Inequality ($\sum 2^{-l_i} \le 1$) and $L_{\text{Huff}} \le L_{\text{SF}}$, and saves detailed metrics to `benchmark_results_v2.json`.

---

## Summary of Verified Results (Windows 11, Python 3.14.2)

- **Lossless Accuracy:** 22 / 22 datasets passed bit-exact round-trip verification and Kraft's Inequality.
- **Scale Linearity (Suite 1, English distribution, $|\Sigma| = 26$):**  
  At $N = 1{,}000{,}000$, Complete File Compression Ratio reaches **1.9004×** (Payload-Only CR: **1.9011×**), encoding in **214.22 ms** (**4.67 MB/s**) and decoding in **538.23 ms** (**1.86 MB/s**).
- **Prefix-Sum Speedup (Suite 2, Uniform $\alpha = 0.0$, $|\Sigma| = 256$):**  
  Tree construction runs in **532.39 µs** vs. **14,884.09 µs** for naive slice-summing (**28.0× speedup**) and **851.90 µs** for `heapq` Huffman (**1.60× faster**).
- **Zipf Skewness & Sub-Optimality (Suite 3, $|\Sigma| = 64, N = 100{,}000$):**  
  Complete File CR improves from **1.3234×** ($\alpha = 0.0$) to **5.8938×** ($\alpha = 3.0$), with peak Shannon-Fano sub-optimality of **+0.1052 bits/char** at $\alpha = 1.5$.
- **Minimal Sub-Optimality Verification (Suite 4):**  
  On `"AAAAABBCCDDEE"` (frequencies `[5, 2, 2, 2, 2]`), Shannon-Fano produces **30 bits** vs. Huffman's **29 bits**; on `"ABCDEFGHIJ"` (10 uniform characters), both produce **34 bits**.

---

## References

1. C. E. Shannon (1948), *A Mathematical Theory of Communication*, Bell System Technical Journal ([PDF](https://people.math.harvard.edu/~ctm/home/text/others/shannon/entropy/entropy.pdf))
2. R. M. Fano (1949), *The Transmission of Information*, MIT RLE Technical Report No. 65
3. MIT OpenCourseWare 6.050J, *Information and Entropy — Chapter 3* ([Course](https://ocw.mit.edu/courses/6-050j-information-and-entropy-spring-2008/))
4. NIST DADS, *Shannon-Fano Coding* ([Entry](https://xlinux.nist.gov/dads/HTML/shannonFano.html))
5. Python Software Foundation, *Python Standard Library Documentation* ([Docs](https://docs.python.org/3/library/))
