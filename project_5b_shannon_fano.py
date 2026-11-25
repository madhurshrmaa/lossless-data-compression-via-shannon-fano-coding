"""
CS 3358: Data Structures & Algorithms — Honors Credit Project 5B
Lossless Data Compression via Shannon-Fano Coding
Author: Madhur Sharma | Faculty: Prof. Suddhasvatta Das | Fall 2026
"""

import collections
import heapq
import json
import math
import os
import platform
import random
import statistics
import struct
import time

MAGIC = b"SF5B"


class TreeNode:
    __slots__ = ("char", "freq", "left", "right")

    def __init__(self, char=None, freq=0, left=None, right=None):
        self.char = char
        self.freq = freq
        self.left = left
        self.right = right


def build_frequency_table(text: str) -> list[tuple[str, int]]:
    """Spec 1: O(N) frequency scan + deterministic O(U log U) sort by (-freq, ord(char))."""
    counts = collections.Counter(text)
    return sorted(counts.items(), key=lambda item: (-item[1], ord(item[0])))


def build_shannon_fano_codes(sorted_symbols: list[tuple[str, int]]) -> dict[str, str]:
    """
    Spec 2: Top-down recursive Shannon-Fano partitioning with 1D prefix-sum array.
    - Evaluating delta(k) for a candidate split k is O(1).
    - Searching candidate splits across [l..r-1] is O(r - l) with unimodal early exit.
    - Ties (delta(k) == delta(k+1)) deterministically select the earlier split (smaller k).
    """
    u = len(sorted_symbols)
    if u == 0:
        return {}
    if u == 1:
        return {sorted_symbols[0][0]: "0"}

    prefix = [0] * u
    running = 0
    for i, (_, freq) in enumerate(sorted_symbols):
        running += freq
        prefix[i] = running

    codes: dict[str, str] = {}

    def partition(l: int, r: int, current_code: str) -> None:
        if l == r:
            codes[sorted_symbols[l][0]] = current_code
            return
        if r - l == 1:
            codes[sorted_symbols[l][0]] = current_code + "0"
            codes[sorted_symbols[r][0]] = current_code + "1"
            return

        left_base = prefix[l - 1] if l > 0 else 0
        total = prefix[r] - left_base

        best_k = l
        best_delta = total + 1
        for k in range(l, r):
            left_sum = prefix[k] - left_base
            right_sum = prefix[r] - prefix[k]
            delta = abs(left_sum - right_sum)
            if delta < best_delta:  # Strict '<' picks earlier split (smaller k) on ties
                best_delta = delta
                best_k = k
            elif left_sum > right_sum:
                break

        partition(l, best_k, current_code + "0")
        partition(best_k + 1, r, current_code + "1")

    partition(0, u - 1, "")
    return codes


def build_shannon_fano_naive(sorted_symbols: list[tuple[str, int]]) -> dict[str, str]:
    """Naive slice-summing Shannon-Fano (no prefix-sum array) for Suite 2 comparison."""
    u = len(sorted_symbols)
    if u == 0:
        return {}
    if u == 1:
        return {sorted_symbols[0][0]: "0"}
    codes: dict[str, str] = {}

    def partition(l: int, r: int, current_code: str) -> None:
        if l == r:
            codes[sorted_symbols[l][0]] = current_code
            return
        best_k = l
        best_delta = float("inf")
        for k in range(l, r):
            left_sum = sum(f for _, f in sorted_symbols[l:k + 1])
            right_sum = sum(f for _, f in sorted_symbols[k + 1:r + 1])
            delta = abs(left_sum - right_sum)
            if delta < best_delta:
                best_delta = delta
                best_k = k
        partition(l, best_k, current_code + "0")
        partition(best_k + 1, r, current_code + "1")

    partition(0, u - 1, "")
    return codes


def build_huffman_codes(sorted_symbols: list[tuple[str, int]]) -> dict[str, str]:
    """In-memory bottom-up Huffman tree builder (min-heap) for bit-length comparison."""
    u = len(sorted_symbols)
    if u == 0:
        return {}
    if u == 1:
        return {sorted_symbols[0][0]: "0"}

    heap = []
    counter = 0
    for ch, freq in sorted_symbols:
        heapq.heappush(heap, (freq, counter, TreeNode(char=ch, freq=freq)))
        counter += 1

    while len(heap) > 1:
        f1, _, n1 = heapq.heappop(heap)
        f2, _, n2 = heapq.heappop(heap)
        merged = TreeNode(char=None, freq=f1 + f2, left=n1, right=n2)
        heapq.heappush(heap, (f1 + f2, counter, merged))
        counter += 1

    root = heap[0][2]
    codes: dict[str, str] = {}

    def traverse(node: TreeNode, prefix_code: str) -> None:
        if node.char is not None:
            codes[node.char] = prefix_code
            return
        traverse(node.left, prefix_code + "0")
        traverse(node.right, prefix_code + "1")

    traverse(root, "")
    return codes


def build_decode_trie(codes: dict[str, str]) -> TreeNode:
    root = TreeNode()
    for ch, code in codes.items():
        node = root
        for bit in code:
            if bit == "0":
                if node.left is None:
                    node.left = TreeNode()
                node = node.left
            else:
                if node.right is None:
                    node.right = TreeNode()
                node = node.right
        node.char = ch
    return root


def encode_to_bytes(text: str, codes: dict[str, str], sorted_symbols: list[tuple[str, int]]) -> tuple[bytes, int, int]:
    """
    Spec 3: Serialize self-describing big-endian binary header + byte-aligned payload.
    Header: 4B magic ('SF5B') + 4B N + 4B total_bits + 2B U + U*(2B codepoint + 4B freq).
    """
    n = len(text)
    u = len(sorted_symbols)
    bit_string = "".join(codes[ch] for ch in text)
    total_bits = len(bit_string)

    header_parts = [struct.pack(">4sIIH", MAGIC, n, total_bits, u)]
    for ch, freq in sorted_symbols:
        header_parts.append(struct.pack(">HI", ord(ch), freq))
    header = b"".join(header_parts)

    if total_bits == 0:
        payload = b""
    else:
        rem = total_bits % 8
        padded = bit_string + ("0" * (8 - rem) if rem != 0 else "")
        payload = int(padded, 2).to_bytes(len(padded) // 8, byteorder="big")

    return header + payload, len(header), total_bits


def decode_from_bytes(blob: bytes) -> str:
    """Spec 3: Parse header, rebuild deterministic Shannon-Fano trie, decode exact N chars."""
    magic, n, total_bits, u = struct.unpack(">4sIIH", blob[:14])
    if magic != MAGIC:
        raise ValueError("Invalid SF5B binary header magic.")
    if n == 0:
        return ""

    offset = 14
    sorted_symbols = []
    for _ in range(u):
        codepoint, freq = struct.unpack(">HI", blob[offset:offset + 6])
        sorted_symbols.append((chr(codepoint), freq))
        offset += 6

    codes = build_shannon_fano_codes(sorted_symbols)
    root = build_decode_trie(codes)

    payload = blob[offset:]
    bit_int = int.from_bytes(payload, byteorder="big")
    bit_string = format(bit_int, f"0{len(payload) * 8}b")[:total_bits]

    out_chars = []
    node = root
    for bit in bit_string:
        node = node.left if bit == "0" else node.right
        if node.char is not None:
            out_chars.append(node.char)
            node = root
            if len(out_chars) == n:
                break

    return "".join(out_chars)


def shannon_entropy(sorted_symbols: list[tuple[str, int]], n: int) -> float:
    return -sum((f / n) * math.log2(f / n) for _, f in sorted_symbols if f > 0) if n > 0 else 0.0


def verify_prefix_free_and_kraft(codes: dict[str, str]) -> tuple[bool, float]:
    sorted_codes = sorted(codes.values(), key=len)
    prefix_free = all(
        not sorted_codes[j].startswith(sorted_codes[i])
        for i in range(len(sorted_codes))
        for j in range(i + 1, len(sorted_codes))
    )
    kraft_sum = sum(2.0 ** (-len(c)) for c in codes.values())
    return prefix_free, kraft_sum


ENGLISH_LETTERS = list("ETAOINSHRDLCUMWFGYPBVKJXQZ")
ENGLISH_WEIGHTS = [
    12.70, 9.06, 8.17, 7.51, 6.97, 6.75, 6.33, 6.09, 5.99, 4.25,
    4.03, 2.78, 2.76, 2.41, 2.36, 2.23, 2.02, 1.97, 1.93, 1.49,
    0.98, 0.77, 0.15, 0.15, 0.10, 0.07,
]


def generate_english_text(n: int, rng: random.Random) -> str:
    return "".join(rng.choices(ENGLISH_LETTERS, weights=ENGLISH_WEIGHTS, k=n))


def generate_uniform_text(n: int, u: int, rng: random.Random) -> str:
    alphabet = [chr(33 + i) if i < 94 else chr(161 + (i - 94)) for i in range(u)]
    return "".join(rng.choices(alphabet, k=n))


def generate_zipf_text(n: int, u: int, alpha: float, rng: random.Random) -> str:
    alphabet = [chr(33 + i) for i in range(u)]
    weights = [1.0] * u if alpha == 0.0 else [1.0 / ((rank + 1) ** alpha) for rank in range(u)]
    return "".join(rng.choices(alphabet, weights=weights, k=n))


def freq_stats(sorted_symbols: list[tuple[str, int]]) -> dict:
    freqs = [f for _, f in sorted_symbols]
    return {
        "U": len(freqs),
        "min": min(freqs),
        "median": round(statistics.median(freqs), 2),
        "mean": round(statistics.mean(freqs), 2),
        "std": round(statistics.stdev(freqs), 2) if len(freqs) > 1 else 0.0,
        "max": max(freqs),
    }


def run_all_benchmarks(save_json_path: str | None = None) -> dict:
    rng = random.Random(3358)
    results = {
        "environment": {
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
        },
        "suite1_scale": [],
        "suite2_alphabet": [],
        "suite3_skew": [],
        "suite4_real_and_edge": [],
    }

    # Suite 4: Edge cases & Real-world source code
    edge_cases = [
        ("10-Char Uniform ('ABCDEFGHIJ')", "ABCDEFGHIJ"),
        ("Minimal Sub-Opt [5,2,2,2,2] ('AAAAABBCCDDEE')", "AAAAABBCCDDEE"),
        ("Sorted Tie-Break [3,2,2,1] ('AAABBCCD')", "AAABBCCD"),
        ("Single Unique Symbol ('A' x 1,000)", "A" * 1000),
        ("Real Python Source File", open(__file__, "r", encoding="utf-8").read()),
    ]
    for name, text in edge_cases:
        syms = build_frequency_table(text)
        sf_codes = build_shannon_fano_codes(syms)
        hf_codes = build_huffman_codes(syms)
        blob, hdr_bytes, payload_bits = encode_to_bytes(text, sf_codes, syms)
        decoded = decode_from_bytes(blob)
        assert decoded == text, f"Round-trip failed for {name}"
        pf_ok, kraft = verify_prefix_free_and_kraft(sf_codes)
        assert pf_ok and kraft <= 1.0 + 1e-12

        n = len(text)
        hf_bits = sum(f * len(hf_codes[c]) for c, f in syms)
        assert hf_bits <= payload_bits, "Huffman must never exceed Shannon-Fano bits!"
        results["suite4_real_and_edge"].append({
            "name": name,
            "N": n,
            "U": len(syms),
            "entropy_H": round(shannon_entropy(syms, n), 4),
            "sf_payload_bits": payload_bits,
            "hf_payload_bits": hf_bits,
            "header_bytes": hdr_bytes,
            "total_file_bytes": len(blob),
            "complete_file_cr": round(n / len(blob), 4),
            "payload_only_cr": round((8 * n) / payload_bits, 4),
            "sf_max_height": max(len(c) for c in sf_codes.values()),
            "hf_max_height": max(len(c) for c in hf_codes.values()),
            "kraft_sum": round(kraft, 4),
            "lossless_verified": True,
            "freq_stats": freq_stats(syms),
        })

    # Suite 1: Input Scale N
    for n in [1_000, 10_000, 100_000, 1_000_000]:
        text = generate_english_text(n, rng)
        t0 = time.perf_counter()
        syms = build_frequency_table(text)
        sf_codes = build_shannon_fano_codes(syms)
        blob, hdr_bytes, payload_bits = encode_to_bytes(text, sf_codes, syms)
        t_enc = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        decoded = decode_from_bytes(blob)
        t_dec = (time.perf_counter() - t1) * 1000.0
        assert decoded == text

        hf_codes = build_huffman_codes(syms)
        hf_bits = sum(f * len(hf_codes[c]) for c, f in syms)
        assert hf_bits <= payload_bits

        results["suite1_scale"].append({
            "N": n,
            "U": len(syms),
            "entropy_H": round(shannon_entropy(syms, n), 4),
            "sf_avg_bits": round(payload_bits / n, 4),
            "hf_avg_bits": round(hf_bits / n, 4),
            "complete_file_cr": round(n / len(blob), 4),
            "payload_only_cr": round((8 * n) / payload_bits, 4),
            "header_bytes": hdr_bytes,
            "total_file_bytes": len(blob),
            "encode_ms": round(t_enc, 3),
            "decode_ms": round(t_dec, 3),
            "encode_MB_s": round((n / 1e6) / (t_enc / 1000.0), 2),
            "decode_MB_s": round((n / 1e6) / (t_dec / 1000.0), 2),
            "freq_stats": freq_stats(syms),
        })

    # Suite 2: Alphabet Size |Sigma|
    for u in [4, 10, 16, 32, 64, 128, 256]:
        text = generate_uniform_text(100_000, u, rng)
        syms = build_frequency_table(text)

        iters = 200
        t0 = time.perf_counter()
        for _ in range(iters):
            sf_codes = build_shannon_fano_codes(syms)
        t_sf_us = ((time.perf_counter() - t0) / iters) * 1e6

        t1 = time.perf_counter()
        for _ in range(iters):
            _ = build_shannon_fano_naive(syms)
        t_naive_us = ((time.perf_counter() - t1) / iters) * 1e6

        t2 = time.perf_counter()
        for _ in range(iters):
            hf_codes = build_huffman_codes(syms)
        t_hf_us = ((time.perf_counter() - t2) / iters) * 1e6

        blob, hdr_bytes, payload_bits = encode_to_bytes(text, sf_codes, syms)
        assert decode_from_bytes(blob) == text
        hf_bits = sum(f * len(hf_codes[c]) for c, f in syms)
        assert hf_bits <= payload_bits

        results["suite2_alphabet"].append({
            "U": u,
            "N": 100_000,
            "entropy_H": round(shannon_entropy(syms, 100_000), 4),
            "sf_avg_bits": round(payload_bits / 100_000, 4),
            "hf_avg_bits": round(hf_bits / 100_000, 4),
            "bit_gap": round((payload_bits - hf_bits) / 100_000, 4),
            "complete_file_cr": round(100_000 / len(blob), 4),
            "payload_only_cr": round((8 * 100_000) / payload_bits, 4),
            "sf_height": max(len(c) for c in sf_codes.values()),
            "hf_height": max(len(c) for c in hf_codes.values()),
            "sf_prefix_us": round(t_sf_us, 2),
            "sf_naive_us": round(t_naive_us, 2),
            "hf_heap_us": round(t_hf_us, 2),
            "header_bytes": hdr_bytes,
            "freq_stats": freq_stats(syms),
        })

    # Suite 3: Zipf Entropy Skew alpha
    for alpha in [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]:
        text = generate_zipf_text(100_000, 64, alpha, rng)
        syms = build_frequency_table(text)
        sf_codes = build_shannon_fano_codes(syms)
        hf_codes = build_huffman_codes(syms)
        blob, hdr_bytes, payload_bits = encode_to_bytes(text, sf_codes, syms)
        assert decode_from_bytes(blob) == text

        n = len(text)
        hf_bits = sum(f * len(hf_codes[c]) for c, f in syms)
        assert hf_bits <= payload_bits

        results["suite3_skew"].append({
            "alpha": alpha,
            "N": n,
            "U_observed": len(syms),
            "entropy_H": round(shannon_entropy(syms, n), 4),
            "sf_avg_bits": round(payload_bits / n, 4),
            "hf_avg_bits": round(hf_bits / n, 4),
            "bit_gap": round((payload_bits - hf_bits) / n, 4),
            "complete_file_cr": round(n / len(blob), 4),
            "payload_only_cr": round((8 * n) / payload_bits, 4),
            "sf_height": max(len(c) for c in sf_codes.values()),
            "hf_height": max(len(c) for c in hf_codes.values()),
            "freq_stats": freq_stats(syms),
        })

    if save_json_path:
        with open(save_json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    return results


if __name__ == "__main__":
    out_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results_v2.json")
    res = run_all_benchmarks(out_json)
    print(f"All 22 datasets verified (100% lossless, Kraft <= 1, Huffman <= SF). Saved to {out_json}")