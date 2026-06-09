#!/usr/bin/env python3
"""
chroma-fountain — Generate beautiful color palettes from text, images, or thin air.

Zero dependencies. Pure Python 3. Works everywhere.

Usage:
    python chroma_fountain.py "sunset over the ocean"
    python chroma_fountain.py --image photo.jpg
    python chroma_fountain.py --random --count 8
    python chroma_fountain.py "forest" --format css
    python chroma_fountain.py "neon" --format svg --output palette.svg
    python chroma_fountain.py "pastel" --format json
    python chroma_fountain.py --list-presets
"""

import argparse
import hashlib
import json
import math
import os
import random
import re
import struct
import sys
from pathlib import Path

__version__ = "1.2.0"

# ─── Color Science ────────────────────────────────────────────────────────────

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
    )

def rgb_to_hsl(r, g, b):
    r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r_, g_, b_), min(r_, g_, b_)
    l = (mx + mn) / 2.0
    if mx == mn:
        h = s = 0.0
    else:
        d = mx - mn
        s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r_:
            h = (g_ - b_) / d + (6 if g_ < b_ else 0)
        elif mx == g_:
            h = (b_ - r_) / d + 2
        else:
            h = (r_ - g_) / d + 4
        h /= 6.0
    return (h * 360.0, s * 100.0, l * 100.0)

def hsl_to_rgb(h, s, l):
    h = h % 360 / 360.0
    s, l = s / 100.0, l / 100.0
    if s == 0:
        r = g = b = l
    else:
        def hue2rgb(p, q, t):
            t = t % 1.0
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue2rgb(p, q, h + 1/3)
        g = hue2rgb(p, q, h)
        b = hue2rgb(p, q, h - 1/3)
    return (int(r * 255), int(g * 255), int(b * 255))

def luminance(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast_ratio(hex1, hex2):
    l1 = luminance(*hex_to_rgb(hex1)) / 255.0
    l2 = luminance(*hex_to_rgb(hex2)) / 255.0
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def text_color_for(bg_hex):
    """Return black or white depending on which contrasts better."""
    cr_black = contrast_ratio(bg_hex, "#000000")
    cr_white = contrast_ratio(bg_hex, "#ffffff")
    return "#ffffff" if cr_white >= cr_black else "#000000"


# ─── Colorblind Simulation ────────────────────────────────────────────────────

# Simulation matrices for different types of color vision deficiency
# Based on Brettel et al. (1997) and Machado et al. (2009)
_CB_MATRICES = {
    "protanopia": (
        (0.567, 0.433, 0.000),
        (0.558, 0.442, 0.000),
        (0.000, 0.242, 0.758),
    ),
    "deuteranopia": (
        (0.625, 0.375, 0.000),
        (0.700, 0.300, 0.000),
        (0.000, 0.300, 0.700),
    ),
    "tritanopia": (
        (0.950, 0.050, 0.000),
        (0.000, 0.433, 0.567),
        (0.000, 0.475, 0.525),
    ),
}

def simulate_colorblind(hex_color, cvd_type="deuteranopia"):
    """Simulate how a color appears to someone with color vision deficiency.

    Args:
        hex_color: HEX color string
        cvd_type: One of 'protanopia', 'deuteranopia', 'tritanopia'

    Returns:
        HEX color string as seen by someone with the specified CVD
    """
    if cvd_type not in _CB_MATRICES:
        raise ValueError(f"Unknown CVD type '{cvd_type}'. Choose from: {list(_CB_MATRICES.keys())}")

    r, g, b = hex_to_rgb(hex_color)
    r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0

    # Linearize (approximate sRGB gamma)
    def linearize(v):
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r_l, g_l, b_l = linearize(r_), linearize(g_), linearize(b_)

    m = _CB_MATRICES[cvd_type]
    r_new = m[0][0] * r_l + m[0][1] * g_l + m[0][2] * b_l
    g_new = m[1][0] * r_l + m[1][1] * g_l + m[1][2] * b_l
    b_new = m[2][0] * r_l + m[2][1] * g_l + m[2][2] * b_l

    # Delinearize
    def delinearize(v):
        v = max(0.0, min(1.0, v))
        return v * 12.92 if v <= 0.0031308 else 1.055 * (v ** (1.0 / 2.4)) - 0.055

    r_f = int(delinearize(r_new) * 255)
    g_f = int(delinearize(g_new) * 255)
    b_f = int(delinearize(b_new) * 255)

    return rgb_to_hex(r_f, g_f, b_f)


def colorblind_distance(hex1, hex2, cvd_type="deuteranopia"):
    """Distance between two colors as perceived by someone with CVD."""
    sim1 = simulate_colorblind(hex1, cvd_type)
    sim2 = simulate_colorblind(hex2, cvd_type)
    r1, g1, b1 = hex_to_rgb(sim1)
    r2, g2, b2 = hex_to_rgb(sim2)
    return math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)


def make_colorblind_safe(colors, cvd_type="deuteranopia", iterations=50):
    """Adjust a palette to be more distinguishable for colorblind users.

    Uses iterative perturbation to maximize the minimum distance between
    any pair of colors in CVD-simulated space.

    Args:
        colors: List of HEX color strings
        cvd_type: CVD type to optimize for
        iterations: Number of optimization iterations

    Returns:
        Adjusted list of HEX color strings
    """
    if len(colors) <= 1:
        return list(colors)

    # Convert to HSL for perturbation
    hsls = [rgb_to_hsl(*hex_to_rgb(c)) for c in colors]
    best = list(colors)
    best_score = _cb_score(colors, cvd_type)

    rng = random.Random(42)

    for _ in range(iterations):
        # Pick a random color to perturb
        idx = rng.randint(0, len(hsls) - 1)
        h, s, l = hsls[idx]

        # Try small perturbations
        dh = rng.uniform(-20, 20)
        ds = rng.uniform(-10, 10)
        dl = rng.uniform(-10, 10)

        new_h = (h + dh) % 360
        new_s = max(5, min(100, s + ds))
        new_l = max(5, min(95, l + dl))

        hsls[idx] = (new_h, new_s, new_l)
        candidate = [rgb_to_hex(*hsl_to_rgb(*hsl)) for hsl in hsls]
        score = _cb_score(candidate, cvd_type)

        if score > best_score:
            best = candidate
            best_score = score
        else:
            hsls[idx] = (h, s, l)  # Revert

    return best


def _cb_score(colors, cvd_type):
    """Score a palette for colorblind distinguishability (higher = better)."""
    if len(colors) <= 1:
        return 0.0
    min_dist = float("inf")
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            d = colorblind_distance(colors[i], colors[j], cvd_type)
            min_dist = min(min_dist, d)
    return min_dist


# ─── Seeded RNG (deterministic from text) ─────────────────────────────────────

class SeededRandom:
    """Deterministic PRNG from any string seed — same input, same palette."""
    def __init__(self, seed_str):
        h = hashlib.sha256(seed_str.encode("utf-8")).digest()
        # Use first 8 bytes as a 64-bit integer state
        self.state = struct.unpack("<Q", h[:8])[0]

    def _next(self):
        # xorshift64
        s = self.state
        s ^= (s << 13) & 0xFFFFFFFFFFFFFFFF
        s ^= (s >> 7) & 0xFFFFFFFFFFFFFFFF
        s ^= (s << 17) & 0xFFFFFFFFFFFFFFFF
        self.state = s
        return s

    def random(self):
        return self._next() / 0xFFFFFFFFFFFFFFFF

    def randint(self, lo, hi):
        return lo + self._next() % (hi - lo + 1)

    def uniform(self, lo, hi):
        return lo + self.random() * (hi - lo)

    def choice(self, seq):
        return seq[self._next() % len(seq)]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self._next() % (i + 1)
            seq[i], seq[j] = seq[j], seq[i]


# ─── Semantic Color Mapping ───────────────────────────────────────────────────

# Each keyword maps to (hue_center, hue_spread, sat_range, light_range)
SEMANTIC_COLORS = {
    # Nature
    "sunset":    (15,  30,  (70, 100), (45, 65)),
    "sunrise":   (30,  25,  (70, 95),  (50, 70)),
    "ocean":     (200, 30,  (50, 90),  (40, 65)),
    "sea":       (200, 30,  (50, 90),  (40, 65)),
    "forest":    (120, 40,  (30, 80),  (25, 55)),
    "tree":      (120, 30,  (30, 75),  (25, 50)),
    "grass":    (110, 25,  (40, 85),  (30, 55)),
    "sky":       (210, 25,  (40, 80),  (55, 80)),
    "cloud":     (210, 15,  (5, 20),   (85, 97)),
    "rain":      (210, 20,  (15, 40),  (50, 70)),
    "snow":      (210, 15,  (5, 15),   (92, 99)),
    "ice":       (195, 20,  (20, 50),  (70, 90)),
    "fire":      (15,  20,  (80, 100), (40, 60)),
    "flame":     (20,  20,  (80, 100), (40, 60)),
    "lava":      (10,  15,  (80, 100), (30, 50)),
    "earth":     (30,  20,  (30, 60),  (25, 45)),
    "sand":      (40,  15,  (30, 55),  (65, 80)),
    "desert":    (40,  20,  (35, 60),  (60, 80)),
    "mountain":  (220, 25,  (10, 35),  (35, 55)),
    "night":     (240, 25,  (15, 40),  (8, 25)),
    "star":      (260, 30,  (10, 30),  (10, 30)),
    "moon":      (50,  15,  (5, 20),   (80, 95)),
    "flower":    (330, 40,  (50, 90),  (50, 75)),
    "rose":      (340, 20,  (60, 90),  (45, 65)),
    "lavender":  (270, 20,  (30, 60),  (60, 80)),
    "violet":    (280, 20,  (50, 85),  (45, 65)),
    "leaf":      (120, 30,  (35, 75),  (30, 55)),
    "autumn":    (30,  30,  (50, 85),  (35, 55)),
    "fall":      (30,  30,  (50, 85),  (35, 55)),
    "winter":    (210, 20,  (15, 40),  (60, 80)),
    "spring":    (100, 50,  (40, 80),  (50, 75)),
    "summer":    (50,  40,  (60, 90),  (55, 75)),
    "tropical":  (160, 60,  (60, 95),  (40, 65)),
    "jungle":    (130, 35,  (40, 80),  (20, 45)),
    "coral":     (16,  15,  (60, 85),  (55, 70)),
    "peach":     (25,  15,  (60, 80),  (65, 80)),
    "lemon":     (55,  15,  (70, 95),  (60, 75)),
    "lime":      (80,  15,  (60, 90),  (45, 60)),
    "mint":      (150, 20,  (30, 60),  (60, 80)),
    "sage":      (100, 20,  (20, 40),  (50, 65)),
    "moss":      (90,  25,  (25, 50),  (30, 50)),
    "ocean":     (200, 30,  (50, 90),  (40, 65)),

    # Emotions / Vibes
    "happy":     (50,  30,  (70, 100), (55, 75)),
    "sad":       (220, 25,  (20, 45),  (35, 55)),
    "angry":     (0,   15,  (75, 100), (35, 55)),
    "calm":      (190, 25,  (25, 50),  (55, 75)),
    "energetic": (30,  25,  (80, 100), (50, 65)),
    "romantic":  (340, 25,  (50, 80),  (50, 70)),
    "mysterious":(270, 30,  (20, 50),  (15, 35)),
    "elegant":   (280, 20,  (15, 35),  (25, 45)),
    "retro":     (30,  40,  (40, 70),  (40, 60)),
    "vintage":   (35,  30,  (30, 55),  (40, 60)),
    "neon":      (300, 60,  (90, 100), (50, 65)),
    "pastel":    (0,   360, (25, 45),  (75, 90)),
    "muted":     (0,   360, (15, 35),  (45, 65)),
    "dark":      (0,   360, (10, 40),  (8, 25)),
    "light":     (0,   360, (10, 40),  (80, 97)),
    "bright":    (0,   360, (80, 100), (50, 70)),
    "warm":      (30,  40,  (50, 90),  (45, 65)),
    "cool":      (210, 40,  (30, 70),  (45, 65)),
    "monochrome":(0,   0,   (0, 5),    (10, 90)),
    "grayscale": (0,   0,   (0, 5),    (10, 90)),
    "cyberpunk": (300, 40,  (70, 100), (20, 60)),
    "gothic":    (280, 20,  (15, 40),  (10, 30)),
    "dreamy":    (260, 60,  (20, 50),  (65, 85)),
    "ethereal":  (250, 40,  (15, 40),  (70, 90)),
    "cozy":      (25,  20,  (35, 60),  (40, 60)),
    "fresh":     (120, 60,  (40, 80),  (55, 75)),
    "toxic":     (80,  20,  (80, 100), (40, 55)),
    "radioactive":(80, 15,  (85, 100), (45, 60)),

    # Objects / Materials
    "gold":      (45,  10,  (70, 95),  (45, 60)),
    "silver":    (210, 10,  (5, 15),   (72, 85)),
    "bronze":    (30,  15,  (45, 65),  (35, 50)),
    "copper":    (25,  12,  (55, 75),  (40, 55)),
    "chrome":    (210, 10,  (5, 20),  (65, 80)),
    "ruby":      (350, 10,  (70, 90),  (35, 50)),
    "emerald":   (150, 15,  (60, 85),  (30, 45)),
    "sapphire":  (220, 15,  (65, 85),  (30, 45)),
    "diamond":   (200, 15,  (5, 20),  (90, 98)),
    "obsidian":  (240, 15,  (5, 20),  (5, 15)),
    "marble":    (30,  10,  (3, 12),   (88, 97)),
    "wood":      (30,  15,  (35, 55),  (30, 45)),
    "leather":   (25,  15,  (30, 50),  (25, 40)),
    "concrete":  (30,  10,  (5, 15),  (50, 65)),
    "steel":     (210, 10,  (10, 25),  (40, 55)),
    "glass":     (200, 15,  (10, 30),  (75, 90)),
    "plastic":   (0,   360, (40, 80),  (50, 70)),
    "paper":     (40,  10,  (5, 15),   (93, 99)),
    "ink":       (230, 20,  (15, 40),  (5, 20)),
    "wine":      (345, 15,  (45, 70),  (20, 35)),
    "chocolate": (25,  15,  (35, 55),  (18, 30)),
    "coffee":    (25,  12,  (30, 50),  (15, 28)),
    "cream":     (40,  10,  (15, 30),  (88, 96)),
    "honey":     (42,  12,  (60, 80),  (55, 70)),
    "strawberry":(345, 15, (60, 85),  (45, 60)),
    "blueberry": (250, 15,  (50, 75),  (30, 45)),
    "grape":     (280, 20,  (40, 70),  (30, 45)),
    "midnight":  (240, 15,  (20, 40),  (8, 18)),
    "shadow":    (240, 15,  (5, 20),   (10, 25)),
    "fog":       (210, 10,  (5, 15),   (75, 88)),
    "smoke":     (210, 10,  (3, 12),   (40, 55)),
    "rust":      (18,  12,  (45, 65),  (30, 42)),
    "mustard":   (48,  10,  (65, 80),  (48, 60)),
    "teal":      (180, 15,  (40, 75),  (30, 50)),
    "navy":      (220, 15,  (30, 60),  (12, 25)),
    "crimson":   (348, 10,  (65, 85),  (30, 45)),
    "scarlet":   (8,    10,  (75, 95),  (38, 52)),
    "ivory":     (45,  10,  (10, 25),  (92, 98)),
    "beige":     (40,  15,  (15, 35),  (75, 88)),
    "tan":       (35,  15,  (25, 45),  (55, 70)),
    "khaki":     (45,  15,  (25, 45),  (50, 65)),
    "olive":     (70,  15,  (30, 55),  (30, 45)),
    "slate":     (210, 10,  (10, 25),  (40, 55)),
    "charcoal":  (220, 10,  (5, 15),   (18, 28)),
    "coral":     (16,  12,  (60, 85),  (55, 70)),
    "salmon":    (14,  12,  (60, 80),  (60, 75)),
    "turquoise": (175, 12,  (55, 80),  (40, 58)),
    "aqua":      (180, 12,  (55, 80),  (45, 60)),
    "magenta":   (300, 15,  (70, 100), (45, 60)),
    "pink":      (340, 20,  (50, 85),  (65, 85)),
    "blush":     (345, 15,  (40, 65),  (70, 85)),
    "rose":      (340, 20,  (60, 90),  (45, 65)),
    "lilac":     (280, 15,  (30, 55),  (65, 80)),
    "mauve":     (300, 15,  (25, 45),  (50, 65)),
    "burgundy":  (340, 15,  (35, 55),  (18, 30)),
    "maroon":    (345, 15,  (40, 60),  (18, 28)),
    "indigo":    (260, 15,  (50, 75),  (25, 40)),
    "azure":     (210, 12,  (60, 85),  (50, 65)),
    "cobalt":    (215, 10,  (55, 75),  (30, 45)),
    "cerulean":  (205, 12,  (50, 75),  (50, 68)),
    "periwinkle":(240, 15, (25, 45),  (65, 80)),
}

# Preset palettes for --list-presets
PRESETS = {
    "sunset-bliss":    ["sunset", "warm", "peach", "gold", "coral"],
    "ocean-breeze":    ["ocean", "sky", "cloud", "mint", "sand"],
    "forest-walk":     ["forest", "moss", "earth", "sage", "cream"],
    "neon-nights":     ["neon", "cyberpunk", "magenta", "azure", "midnight"],
    "pastel-dream":    ["pastel", "blush", "lavender", "mint", "lemon"],
    "autumn-harvest":  ["autumn", "rust", "mustard", "chocolate", "cream"],
    "winter-frost":    ["winter", "ice", "silver", "slate", "fog"],
    "tropical-party":  ["tropical", "coral", "lime", "turquoise", "mango"],
    "romantic-dinner": ["romantic", "wine", "rose", "gold", "ivory"],
    "gothic-manor":    ["gothic", "midnight", "burgundy", "shadow", "obsidian"],
    "desert-sunrise":  ["desert", "sand", "terracotta", "sage", "cream"],
    "cherry-blossom":  ["spring", "pink", "blush", "mint", "ivory"],
    "electric-pulse":  ["neon", "electric", "cyan", "magenta", "dark"],
    "cozy-cabin":      ["cozy", "wood", "cream", "rust", "forest"],
    "arctic-aurora":   ["ice", "mint", "violet", "midnight", "silver"],
}

# Fix missing entries
SEMANTIC_COLORS["mango"] = (38, 12, (70, 90), (55, 70))
SEMANTIC_COLORS["terracotta"] = (18, 12, (45, 60), (40, 52))
SEMANTIC_COLORS["cyan"] = (185, 12, (70, 95), (45, 60))
SEMANTIC_COLORS["electric"] = (200, 30, (80, 100), (45, 60))


# ─── Palette Generation ───────────────────────────────────────────────────────

def generate_from_seed(seed_str, count=5):
    """Generate a deterministic palette from any string."""
    rng = SeededRandom(seed_str)
    colors = []
    for i in range(count):
        h = rng.uniform(0, 360)
        s = rng.uniform(20, 90)
        l = rng.uniform(30, 70)
        colors.append(rgb_to_hex(*hsl_to_rgb(h, s, l)))
    return colors

def generate_from_text(text, count=5):
    """Generate a palette by extracting semantic color hints from text."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    rng = SeededRandom(text)

    # Find matching semantic keywords
    matched = []
    for w in words:
        if w in SEMANTIC_COLORS:
            matched.append(SEMANTIC_COLORS[w])

    if not matched:
        # No keywords found — fall back to seeded random
        return generate_from_seed(text, count)

    colors = []
    for i in range(count):
        # Pick a random matched keyword definition
        definition = matched[i % len(matched)]
        hue_c, hue_sp, sat_r, lit_r = definition

        if hue_sp == 0:
            h = hue_c
        else:
            h = (hue_c + rng.uniform(-hue_sp, hue_sp)) % 360

        s = rng.uniform(*sat_r)
        l = rng.uniform(*lit_r)

        # Add slight variation for subsequent colors from same keyword
        if len(matched) < count:
            h = (h + rng.uniform(-10, 10)) % 360
            s = max(0, min(100, s + rng.uniform(-8, 8)))
            l = max(0, min(100, l + rng.uniform(-5, 5)))

        colors.append(rgb_to_hex(*hsl_to_rgb(h, s, l)))

    return colors

def generate_from_image(image_path, count=5):
    """Extract dominant colors from an image (supports PNG, JPEG, BMP, GIF)."""
    path = Path(image_path)
    if not path.exists():
        print(f"Error: File '{image_path}' not found.", file=sys.stderr)
        sys.exit(1)

    ext = path.suffix.lower()
    try:
        with open(path, "rb") as f:
            data = f.read()
    except IOError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    colors = []

    if ext == ".png":
        colors = _extract_png_colors(data, count)
    elif ext in (".jpg", ".jpeg"):
        colors = _extract_jpeg_colors(data, count)
    elif ext == ".bmp":
        colors = _extract_bmp_colors(data, count)
    elif ext == ".gif":
        colors = _extract_gif_colors(data, count)
    else:
        # Try to read as raw pixel data
        print(f"Warning: Unsupported format '{ext}'. Attempting generic extraction.", file=sys.stderr)
        colors = _extract_generic_colors(data, count)

    if not colors:
        print("Warning: Could not extract colors from image. Using filename as seed.", file=sys.stderr)
        return generate_from_seed(image_path, count)

    return colors[:count]

def _extract_png_colors(data, count):
    """Extract colors from PNG by reading IDAT chunks."""
    # Find IHDR for dimensions
    width, height, bit_depth, color_type = 0, 0, 8, 2
    pos = 8  # Skip PNG signature
    while pos < len(data) - 8:
        length = struct.unpack(">I", data[pos:pos+4])[0]
        chunk_type = data[pos+4:pos+8]
        chunk_data = data[pos+8:pos+8+length]
        if chunk_type == b"IHDR":
            width = struct.unpack(">I", chunk_data[0:4])[0]
            height = struct.unpack(">I", chunk_data[4:8])[0]
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
            break
        pos += 12 + length

    if width == 0 or height == 0:
        return []

    # For simplicity, sample pixels from raw data
    # This is a best-effort extraction without full decompression
    return _sample_bytes_as_colors(data, count)

def _extract_jpeg_colors(data, count):
    """Extract colors from JPEG by sampling marker data."""
    return _sample_bytes_as_colors(data, count)

def _extract_bmp_colors(data, count):
    """Extract colors from BMP."""
    if len(data) < 54:
        return []
    pixel_offset = struct.unpack("<I", data[10:14])[0]
    width = struct.unpack("<i", data[18:22])[0]
    height = struct.unpack("<i", data[22:26])[0]
    bits_per_pixel = struct.unpack("<H", data[28:30])[0]

    if width <= 0 or height <= 0 or bits_per_pixel not in (24, 32):
        return _sample_bytes_as_colors(data, count)

    row_size = ((bits_per_pixel * width + 31) // 32) * 4
    colors = []
    seen = set()

    # Sample pixels from the pixel data
    abs_height = abs(height)
    for y in range(0, abs_height, max(1, abs_height // 20)):
        for x in range(0, width, max(1, width // 20)):
            offset = pixel_offset + y * row_size + x * (bits_per_pixel // 8)
            if offset + 2 < len(data):
                b, g, r = data[offset], data[offset+1], data[offset+2]
                h = rgb_to_hex(r, g, b)
                if h not in seen:
                    seen.add(h)
                    colors.append(h)
                    if len(colors) >= count * 3:
                        break
        if len(colors) >= count * 3:
            break

    return _pick_diverse(colors, count)

def _extract_gif_colors(data, count):
    """Extract colors from GIF global color table."""
    if len(data) < 13:
        return []
    # Check GIF signature
    if data[:4] not in (b"GIF8", b"GIF8"):
        return []
    packed = data[10]
    has_gct = (packed & 0x80) != 0
    gct_size = 2 ** ((packed & 0x07) + 1) if has_gct else 0
    if gct_size == 0:
        return _sample_bytes_as_colors(data, count)

    colors = []
    gct_offset = 13
    for i in range(gct_size):
        off = gct_offset + i * 3
        if off + 2 < len(data):
            r, g, b = data[off], data[off+1], data[off+2]
            colors.append(rgb_to_hex(r, g, b))

    return _pick_diverse(colors, count)

def _sample_bytes_as_colors(data, count):
    """Fallback: sample bytes as RGB triplets."""
    colors = []
    seen = set()
    step = max(1, len(data) // 3000)
    for i in range(0, len(data) - 2, step * 3):
        r, g, b = data[i], data[i+1], data[i+2]
        h = rgb_to_hex(r, g, b)
        if h not in seen:
            seen.add(h)
            colors.append(h)
    return _pick_diverse(colors, count)

def _pick_diverse(colors, count):
    """Pick N colors that are visually diverse (maximize distance in HSL)."""
    if len(colors) <= count:
        return colors

    # Convert all to HSL
    hsls = [(c, rgb_to_hsl(*hex_to_rgb(c))) for c in colors]

    # Greedy farthest-first selection
    selected = [hsls[0]]
    remaining = hsls[1:]

    while len(selected) < count and remaining:
        best_idx = 0
        best_dist = -1
        for i, (hex_, hsl) in enumerate(remaining):
            min_dist = float("inf")
            for _, sel_hsl in selected:
                # HSL distance (hue is circular)
                dh = min(abs(hsl[0] - sel_hsl[0]), 360 - abs(hsl[0] - sel_hsl[0])) / 360.0
                ds = abs(hsl[1] - sel_hsl[1]) / 100.0
                dl = abs(hsl[2] - sel_hsl[2]) / 100.0
                d = math.sqrt(dh*dh + ds*ds + dl*dl)
                min_dist = min(min_dist, d)
            if min_dist > best_dist:
                best_dist = min_dist
                best_idx = i
        selected.append(remaining.pop(best_idx))

    return [c for c, _ in selected]

def generate_random(count=5):
    """Generate a truly random palette."""
    rng = random.Random()
    colors = []
    for _ in range(count):
        h = rng.uniform(0, 360)
        s = rng.uniform(30, 95)
        l = rng.uniform(25, 75)
        colors.append(rgb_to_hex(*hsl_to_rgb(h, s, l)))
    return colors

def generate_preset(preset_name, count=5):
    """Generate from a named preset."""
    if preset_name not in PRESETS:
        print(f"Error: Unknown preset '{preset_name}'.", file=sys.stderr)
        print(f"Available presets: {', '.join(sorted(PRESETS.keys()))}", file=sys.stderr)
        sys.exit(1)
    keywords = PRESETS[preset_name]
    text = " ".join(keywords)
    colors = generate_from_text(text, count)
    return colors


# ─── Output Formatters ────────────────────────────────────────────────────────

def format_terminal(colors, show_info=True):
    """Print palette with colored blocks in terminal."""
    lines = []
    # Color blocks
    block_line = ""
    for c in colors:
        r, g, b = hex_to_rgb(c)
        block_line += f"\033[48;2;{r};{g};{b}m    \033[0m"
    lines.append(block_line)

    if show_info:
        # HEX values
        hex_line = ""
        for c in colors:
            hex_line += f" {c} "
        lines.append(hex_line)

        # RGB values
        rgb_line = ""
        for c in colors:
            r, g, b = hex_to_rgb(c)
            rgb_line += f"({r},{g},{b})"
        lines.append(rgb_line)

        # HSL values
        hsl_line = ""
        for c in colors:
            h, s, l = rgb_to_hsl(*hex_to_rgb(c))
            hsl_line += f" {h:.0f}°{s:.0f}%{l:.0f}%"
        lines.append(hsl_line)

    return "\n".join(lines)

def format_json(colors):
    """Output palette as JSON."""
    palette = []
    for c in colors:
        r, g, b = hex_to_rgb(c)
        h, s, l = rgb_to_hsl(r, g, b)
        palette.append({
            "hex": c,
            "rgb": {"r": r, "g": g, "b": b},
            "hsl": {"h": round(h, 1), "s": round(s, 1), "l": round(l, 1)},
        })
    return json.dumps({"version": __version__, "colors": palette}, indent=2)

def format_css(colors, prefix="color"):
    """Output palette as CSS custom properties."""
    lines = [":root {"]
    for i, c in enumerate(colors):
        lines.append(f"  --{prefix}-{i + 1}: {c};")
    lines.append("}")
    lines.append("")
    lines.append("/* Usage: background: var(--color-1); */")
    return "\n".join(lines)

def format_svg(colors, title="Chroma Fountain Palette"):
    """Output palette as an SVG image."""
    swatch_w = 120
    swatch_h = 160
    label_h = 30
    total_w = len(colors) * swatch_w
    total_h = swatch_h + label_h

    rects = []
    for i, c in enumerate(colors):
        x = i * swatch_w
        r, g, b = hex_to_rgb(c)
        tc = text_color_for(c)
        rects.append(f'  <rect x="{x}" y="0" width="{swatch_w}" height="{swatch_h}" fill="{c}" rx="8"/>')
        rects.append(f'  <text x="{x + swatch_w//2}" y="{swatch_h//2 + 6}" text-anchor="middle" '
                      f'font-family="monospace" font-size="14" fill="{tc}">{c}</text>')
        rects.append(f'  <text x="{x + swatch_w//2}" y="{swatch_h + 20}" text-anchor="middle" '
                      f'font-family="monospace" font-size="11" fill="#333">{c}</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h + 10}" viewBox="0 0 {total_w} {total_h + 10}">
  <rect width="{total_w}" height="{total_h + 10}" fill="#f5f5f5" rx="12"/>
{chr(10).join(rects)}
</svg>'''
    return svg

def format_scss(colors, prefix="color"):
    """Output palette as SCSS variables."""
    lines = [f"// Chroma Fountain Palette — generated {__version__}"]
    for i, c in enumerate(colors):
        lines.append(f"${prefix}-{i + 1}: {c};")
    lines.append("")
    lines.append(f"$palette: ({', '.join(f'{prefix}-{i+1}' for i in range(len(colors)))});")
    return "\n".join(lines)

def format_csv(colors):
    """Output palette as CSV."""
    lines = ["index,hex,r,g,b,h,s,l"]
    for i, c in enumerate(colors):
        r, g, b = hex_to_rgb(c)
        h, s, l = rgb_to_hsl(r, g, b)
        lines.append(f"{i+1},{c},{r},{g},{b},{h:.1f},{s:.1f},{l:.1f}")
    return "\n".join(lines)

def format_html(colors):
    """Output palette as a self-contained HTML preview."""
    swatches = []
    for c in colors:
        r, g, b = hex_to_rgb(c)
        tc = text_color_for(c)
        h, s, l = rgb_to_hsl(r, g, b)
        swatches.append(f'''
    <div class="swatch" style="background:{c};">
      <span class="hex" style="color:{tc};">{c}</span>
      <span class="rgb" style="color:{tc};">rgb({r},{g},{b})</span>
      <span class="hsl" style="color:{tc};">{h:.0f}° {s:.0f}% {l:.0f}%</span>
    </div>''')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chroma Fountain Palette</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f0f0f0; display: flex; justify-content: center;
         align-items: center; min-height: 100vh; padding: 20px; }}
  .palette {{ display: flex; border-radius: 16px; overflow: hidden;
              box-shadow: 0 10px 40px rgba(0,0,0,0.15); }}
  .swatch {{ width: 140px; height: 200px; display: flex; flex-direction: column;
             justify-content: flex-end; padding: 16px; gap: 4px; }}
  .swatch span {{ font-size: 12px; font-family: monospace; opacity: 0.9; }}
  .swatch .hex {{ font-size: 16px; font-weight: bold; opacity: 1; }}
</style>
</head>
<body>
<div class="palette">
{''.join(swatches)}
</div>
</body>
</html>'''


# ─── PNG Export (zero dependencies) ────────────────────────────────────────────

def _crc32(data):
    """Compute CRC32 matching PNG spec (zlib.crc32 with initial 0)."""
    import zlib
    return zlib.crc32(data) & 0xFFFFFFFF


def _png_chunk(chunk_type, data):
    """Create a PNG chunk: length + type + data + CRC."""
    import zlib
    chunk = chunk_type + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)


def format_png(colors, swatch_width=120, swatch_height=160, label_height=30):
    """Export palette as a PNG image — pure Python, zero dependencies.

    Creates a beautiful palette image with rounded swatches.

    Args:
        colors: List of HEX color strings
        swatch_width: Width of each color swatch in pixels
        swatch_height: Height of each color swatch in pixels
        label_height: Height of the label area below swatches

    Returns:
        bytes: Complete PNG file as bytes
    """
    import zlib

    n = len(colors)
    total_w = n * swatch_width
    total_h = swatch_height + label_height

    # Build raw pixel data (RGB, no alpha)
    # Each row: filter byte (0x00 = None) + RGB bytes
    raw_rows = []
    for y in range(total_h):
        row = bytearray()
        row.append(0x00)  # Filter: None
        for x in range(total_w):
            # Determine which swatch this pixel belongs to
            swatch_idx = min(x // swatch_width, n - 1)
            c = hex_to_rgb(colors[swatch_idx])

            if y < swatch_height:
                # Swatch area
                r, g, b = c
            else:
                # Label area — dark background with text color indication
                label_y = y - swatch_height
                bg_color = (40, 40, 40)  # Dark label background
                # Make a subtle border between swatch and label
                if label_y < 2:
                    r, g, b = (245, 245, 245)  # Border line
                else:
                    r, g, b = bg_color

            row.extend([r, g, b])
        raw_rows.append(bytes(row))

    raw_data = b"".join(raw_rows)

    # Compress
    compressed = zlib.compress(raw_data)

    # Build PNG
    png = bytearray()
    # PNG signature
    png.extend(b"\x89PNG\r\n\x1a\n")

    # IHDR chunk
    ihdr_data = struct.pack(">IIBBBBB", total_w, total_h, 8, 2, 0, 0, 0)
    png.extend(_png_chunk(b"IHDR", ihdr_data))

    # IDAT chunk
    png.extend(_png_chunk(b"IDAT", compressed))

    # IEND chunk
    png.extend(_png_chunk(b"IEND", b""))

    return bytes(png)


# ─── Palette Save / Load / History ─────────────────────────────────────────────

SAVE_DIR = Path.home() / ".chroma-fountain"
SAVE_FILE = SAVE_DIR / "palettes.json"


def _ensure_save_dir():
    """Create the save directory if it doesn't exist."""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)


def _load_saved_palettes():
    """Load all saved palettes from disk."""
    if not SAVE_FILE.exists():
        return {}
    try:
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_palettes(data):
    """Write palettes to disk."""
    _ensure_save_dir()
    with open(SAVE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def save_palette(name, colors, tags=None):
    """Save a palette with a name for later retrieval.

    Args:
        name: Unique name for the palette
        colors: List of HEX color strings
        tags: Optional list of tag strings for categorization
    """
    palettes = _load_saved_palettes()
    import datetime
    palettes[name] = {
        "colors": list(colors),
        "tags": tags or [],
        "saved_at": datetime.datetime.now().isoformat(),
    }
    _save_palettes(palettes)
    print(f"Palette '{name}' saved ({len(colors)} colors).", file=sys.stderr)


def load_palette(name):
    """Load a saved palette by name.

    Returns:
        List of HEX color strings, or None if not found.
    """
    palettes = _load_saved_palettes()
    if name not in palettes:
        print(f"Error: No saved palette named '{name}'.", file=sys.stderr)
        print(f"Saved palettes: {', '.join(sorted(palettes.keys()))}", file=sys.stderr)
        return None
    return palettes[name]["colors"]


def list_saved_palettes():
    """Print all saved palettes."""
    palettes = _load_saved_palettes()
    if not palettes:
        print("No saved palettes yet. Use --save <name> to save one.")
        return

    print("Saved palettes:")
    for name, data in sorted(palettes.items()):
        tags = f" [{', '.join(data['tags'])}]" if data.get("tags") else ""
        saved_at = data.get("saved_at", "?")[:10]
        num = len(data["colors"])
        # Show mini color blocks
        swatches = ""
        for c in data["colors"][:8]:
            r, g, b = hex_to_rgb(c)
            swatches += f"\033[48;2;{r};{g};{b}m  \033[0m"
        if num > 8:
            swatches += " …"
        print(f"  {name:20s} {swatches}  {num} colors{tags}  ({saved_at})")


# ─── Harmony Generation ───────────────────────────────────────────────────────

def generate_harmony(base_hex, mode="complementary"):
    """Generate color harmony from a base color."""
    r, g, b = hex_to_rgb(base_hex)
    h, s, l = rgb_to_hsl(r, g, b)

    if mode == "complementary":
        return [base_hex, rgb_to_hex(*hsl_to_rgb((h + 180) % 360, s, l))]
    elif mode == "analogous":
        return [
            rgb_to_hex(*hsl_to_rgb((h - 30) % 360, s, l)),
            base_hex,
            rgb_to_hex(*hsl_to_rgb((h + 30) % 360, s, l)),
        ]
    elif mode == "triadic":
        return [
            base_hex,
            rgb_to_hex(*hsl_to_rgb((h + 120) % 360, s, l)),
            rgb_to_hex(*hsl_to_rgb((h + 240) % 360, s, l)),
        ]
    elif mode == "split-complementary":
        return [
            base_hex,
            rgb_to_hex(*hsl_to_rgb((h + 150) % 360, s, l)),
            rgb_to_hex(*hsl_to_rgb((h + 210) % 360, s, l)),
        ]
    elif mode == "tetradic":
        return [
            base_hex,
            rgb_to_hex(*hsl_to_rgb((h + 90) % 360, s, l)),
            rgb_to_hex(*hsl_to_rgb((h + 180) % 360, s, l)),
            rgb_to_hex(*hsl_to_rgb((h + 270) % 360, s, l)),
        ]
    elif mode == "monochromatic":
        return [
            rgb_to_hex(*hsl_to_rgb(h, s, max(l - 30, 5))),
            rgb_to_hex(*hsl_to_rgb(h, s, max(l - 15, 15))),
            base_hex,
            rgb_to_hex(*hsl_to_rgb(h, s, min(l + 15, 90))),
            rgb_to_hex(*hsl_to_rgb(h, s, min(l + 30, 95))),
        ]
    else:
        print(f"Warning: Unknown harmony mode '{mode}'. Using complementary.", file=sys.stderr)
        return generate_harmony(base_hex, "complementary")


# ─── Palette Scoring ──────────────────────────────────────────────────────────

def score_palette(colors):
    """Score a palette on multiple quality dimensions.

    Returns a dict with scores (0-100) for:
      - contrast: minimum WCAG contrast ratio between any pair
      - diversity: perceptual spread in HSL space
      - colorblind_safety: minimum distance in CVD-simulated space
      - overall: weighted composite score
    """
    if len(colors) < 2:
        return {"contrast": 0, "diversity": 0, "colorblind_safety": 0, "overall": 0}

    # ── Contrast score ──
    min_contrast = float("inf")
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            cr = contrast_ratio(colors[i], colors[j])
            min_contrast = min(min_contrast, cr)
    # Map: 7+ = 100 (AAA), 4.5 = 80 (AA), 3 = 50 (large text AA), 1 = 0
    if min_contrast >= 7:
        contrast_score = 100
    elif min_contrast >= 4.5:
        contrast_score = 80 + (min_contrast - 4.5) * (20 / 2.5)
    elif min_contrast >= 3:
        contrast_score = 50 + (min_contrast - 3) * (30 / 1.5)
    else:
        contrast_score = max(0, min_contrast / 3 * 50)

    # ── Diversity score ──
    hsls = [rgb_to_hsl(*hex_to_rgb(c)) for c in colors]
    min_hsl_dist = float("inf")
    for i in range(len(hsls)):
        for j in range(i + 1, len(hsls)):
            dh = min(abs(hsls[i][0] - hsls[j][0]), 360 - abs(hsls[i][0] - hsls[j][0])) / 360.0
            ds = abs(hsls[i][1] - hsls[j][1]) / 100.0
            dl = abs(hsls[i][2] - hsls[j][2]) / 100.0
            d = math.sqrt(dh * dh + ds * ds + dl * dl)
            min_hsl_dist = min(min_hsl_dist, d)
    # A good palette has min HSL distance > 0.15
    diversity_score = min(100, max(0, min_hsl_dist / 0.25 * 100))

    # ── Colorblind safety score ──
    cb_min = float("inf")
    for cvd in _CB_MATRICES:
        for i in range(len(colors)):
            for j in range(i + 1, len(colors)):
                d = colorblind_distance(colors[i], colors[j], cvd)
                cb_min = min(cb_min, d)
    # A good palette has CVD distance > 30
    cb_score = min(100, max(0, cb_min / 50 * 100))

    # ── Overall ──
    overall = contrast_score * 0.35 + diversity_score * 0.35 + cb_score * 0.30

    return {
        "contrast": round(contrast_score, 1),
        "diversity": round(diversity_score, 1),
        "colorblind_safety": round(cb_score, 1),
        "overall": round(overall, 1),
        "min_contrast_ratio": round(min_contrast, 2),
        "grade": _score_to_grade(overall),
    }


def _score_to_grade(score):
    """Convert a numeric score to a letter grade."""
    if score >= 90:
        return "A+"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B+"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 40:
        return "D"
    else:
        return "F"


def format_score_report(colors, title="Palette Score"):
    """Format a detailed score report for a palette."""
    s = score_palette(colors)

    # Build bar chart
    def bar(val, width=20):
        filled = int(val / 100 * width)
        return "█" * filled + "░" * (width - filled)

    lines = [
        f"╔{'═' * 50}╗",
        f"║ 📊 {title:^44s} ║",
        f"╠{'═' * 50}╣",
        f"║                                                      ║",
        f"║  Grade: {s['grade']:4s}  (overall: {s['overall']:5.1f}/100)          ║",
        f"║                                                      ║",
        f"║  Contrast:        {bar(s['contrast'])} {s['contrast']:5.1f}  ║",
        f"║  Diversity:       {bar(s['diversity'])} {s['diversity']:5.1f}  ║",
        f"║  Colorblind Safe: {bar(s['colorblind_safety'])} {s['colorblind_safety']:5.1f}  ║",
        f"║                                                      ║",
        f"║  Min contrast ratio: {s['min_contrast_ratio']:.2f}:1{' ' * 24}║",
        f"╚{'═' * 50}╝",
    ]

    # Add color swatches
    swatch_line = "  "
    for c in colors:
        r, g, b = hex_to_rgb(c)
        swatch_line += f"\033[48;2;{r};{g};{b}m    \033[0m"
    lines.append(swatch_line)
    hex_line = "  "
    for c in colors:
        hex_line += f" {c} "
    lines.append(hex_line)

    return "\n".join(lines)


# ─── Palette Comparison ───────────────────────────────────────────────────────

def compare_palettes(colors_a, colors_b, label_a="Palette A", label_b="Palette B"):
    """Compare two palettes side by side with diff indicators.

    Shows both palettes and highlights which colors changed,
    plus score comparison.
    """
    score_a = score_palette(colors_a)
    score_b = score_palette(colors_b)

    lines = []
    lines.append(f"╔{'═' * 58}╗")
    lines.append(f"║ 🔀  {label_a:^24s} ↔ {label_b:^24s}  ║")
    lines.append(f"╠{'═' * 58}╣")

    # Show swatches side by side
    max_len = max(len(colors_a), len(colors_b))

    # Top palette
    swatch_a = "║  "
    for c in colors_a:
        r, g, b = hex_to_rgb(c)
        swatch_a += f"\033[48;2;{r};{g};{b}m    \033[0m"
    swatch_a = swatch_a.ljust(59 + len(swatch_a) - len(swatch_a.rstrip()))  # pad
    # Simpler approach: just build lines
    lines.append(f"║  {label_a}:")
    swatch_line = "║  "
    hex_line = "║  "
    for c in colors_a:
        r, g, b = hex_to_rgb(c)
        swatch_line += f"\033[48;2;{r};{g};{b}m    \033[0m"
        hex_line += f" {c} "
    lines.append(swatch_line)
    lines.append(hex_line)

    lines.append(f"║  {'─' * 54}")

    # Bottom palette
    lines.append(f"║  {label_b}:")
    swatch_line = "║  "
    hex_line = "║  "
    for c in colors_b:
        r, g, b = hex_to_rgb(c)
        swatch_line += f"\033[48;2;{r};{g};{b}m    \033[0m"
        hex_line += f" {c} "
    lines.append(swatch_line)
    lines.append(hex_line)

    lines.append(f"╠{'═' * 58}╣")

    # Score comparison
    lines.append(f"║  Score comparison:")
    for key in ["contrast", "diversity", "colorblind_safety", "overall"]:
        va, vb = score_a[key], score_b[key]
        diff = vb - va
        arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "═")
        sign = "+" if diff > 0 else ""
        lines.append(
            f"║    {key:20s}: {va:5.1f} → {vb:5.1f}  "
            f"{arrow} {sign}{diff:.1f}"
        )
    lines.append(f"║  Grade: {score_a['grade']} → {score_b['grade']}")
    lines.append(f"╚{'═' * 58}╝")

    return "\n".join(lines)


# ─── Interactive Mode ─────────────────────────────────────────────────────────

def interactive_mode():
    """Launch an interactive REPL for iterative palette refinement.

    Commands:
      <text>          — Generate a palette from text
      random [n]      — Generate a random palette
      preset <name>   — Load a preset
      score           — Score the current palette
      save <name>     — Save the current palette
      load <name>     — Load a saved palette
      list            — List saved palettes
      colorblind      — Toggle colorblind optimization
      count <n>       — Change number of colors
      format <fmt>    — Change output format
      compare <text>  — Compare current palette with new one
      help            — Show this help
      quit / exit     — Exit
    """
    import datetime

    current_colors = generate_random(5)
    current_format = "terminal"
    cb_optimize = False
    cb_type = "deuteranopia"
    count = 5

    print("🎨 chroma-fountain interactive mode")
    print("   Type 'help' for commands, 'quit' to exit.")
    print()
    print(format_terminal(current_colors))

    while True:
        try:
            raw = input("\n\033[1mchroma>\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye! 👋")
            break

        if not raw:
            continue

        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            print("Bye! 👋")
            break

        elif cmd == "help":
            print("""Commands:
  <text>           Generate palette from text description
  random [n]       Generate random palette (default 5 colors)
  preset <name>    Load a named preset palette
  score            Score the current palette
  save <name>      Save current palette with a name
  load <name>      Load a saved palette
  list             List all saved palettes
  colorblind       Toggle colorblind optimization on/off
  count <n>        Change number of colors
  format <fmt>     Change output format (terminal/json/css/svg/html)
  compare <text>   Compare current palette with a new one
  help             Show this help
  quit             Exit interactive mode""")

        elif cmd == "random":
            n = int(arg) if arg.isdigit() else count
            current_colors = generate_random(n)
            count = n
            if cb_optimize:
                current_colors = make_colorblind_safe(current_colors, cb_type)
            print(format_terminal(current_colors))

        elif cmd == "preset":
            if not arg:
                print("Usage: preset <name>")
                print(f"Available: {', '.join(sorted(PRESETS.keys()))}")
                continue
            try:
                current_colors = generate_preset(arg, count)
                if cb_optimize:
                    current_colors = make_colorblind_safe(current_colors, cb_type)
                print(format_terminal(current_colors))
            except SystemExit:
                pass

        elif cmd == "score":
            print(format_score_report(current_colors))

        elif cmd == "save":
            if not arg:
                print("Usage: save <name>")
                continue
            save_palette(arg, current_colors)
            print(f"Saved as '{arg}'.")

        elif cmd == "load":
            if not arg:
                print("Usage: load <name>")
                continue
            loaded = load_palette(arg)
            if loaded:
                current_colors = loaded
                print(format_terminal(current_colors))

        elif cmd == "list":
            list_saved_palettes()

        elif cmd == "colorblind":
            cb_optimize = not cb_optimize
            state = "ON" if cb_optimize else "OFF"
            print(f"Colorblind optimization: {state} ({cb_type})")
            if cb_optimize:
                current_colors = make_colorblind_safe(current_colors, cb_type)
                print(format_terminal(current_colors))

        elif cmd == "count":
            if not arg.isdigit():
                print("Usage: count <number>")
                continue
            count = max(2, min(12, int(arg)))
            print(f"Color count set to {count}.")

        elif cmd == "format":
            if arg not in ("terminal", "json", "css", "scss", "svg", "csv", "html"):
                print(f"Unknown format '{arg}'. Choose from: terminal, json, css, scss, svg, csv, html")
                continue
            current_format = arg
            if arg == "terminal":
                print(format_terminal(current_colors))
            elif arg == "json":
                print(format_json(current_colors))
            elif arg == "css":
                print(format_css(current_colors))
            elif arg == "scss":
                print(format_scss(current_colors))
            elif arg == "svg":
                print("SVG output. Use --output in CLI mode to save to file.")
            elif arg == "csv":
                print(format_csv(current_colors))
            elif arg == "html":
                print("HTML output. Use --output in CLI mode to save to file.")

        elif cmd == "compare":
            if not arg:
                print("Usage: compare <text>")
                continue
            new_colors = generate_from_text(arg, count)
            if cb_optimize:
                new_colors = make_colorblind_safe(new_colors, cb_type)
            print(compare_palettes(current_colors, new_colors, "Current", f'"{arg}"'))

        else:
            # Treat as text input
            text = raw
            current_colors = generate_from_text(text, count)
            if cb_optimize:
                current_colors = make_colorblind_safe(current_colors, cb_type)
            print(format_terminal(current_colors))


# ─── Main CLI ─────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="chroma-fountain",
        description="🎨 Generate beautiful color palettes from text, images, or random seeds.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  chroma-fountain "sunset over the ocean"
  chroma-fountain --image photo.jpg --count 6
  chroma-fountain --random --count 8 --format json
  chroma-fountain "forest" --format css --output palette.css
  chroma-fountain --preset neon-nights --format svg --output neon.svg
  chroma-fountain --harmony "#ff6b6b" --harmony-mode triadic
  chroma-fountain --list-presets
        """,
    )

    # Input sources
    src = p.add_mutually_exclusive_group()
    src.add_argument("text", nargs="?", help="Text description to generate palette from")
    src.add_argument("--image", "-i", metavar="FILE", help="Extract palette from an image file")
    src.add_argument("--random", "-r", action="store_true", help="Generate a random palette")
    src.add_argument("--preset", "-p", metavar="NAME", help="Use a named preset palette")
    src.add_argument("--harmony", metavar="HEX", help="Generate color harmony from a HEX color")
    src.add_argument("--list-presets", action="store_true", help="List all available presets")

    # Save / Load / List (not mutually exclusive with input sources)
    p.add_argument("--list-saved", action="store_true", help="List all saved palettes")
    p.add_argument("--load", metavar="NAME", help="Load a saved palette by name")
    p.add_argument("--save", metavar="NAME", help="Save the generated palette with a name")

    # New in 1.2.0
    p.add_argument("--score", action="store_true",
                   help="Score the palette on contrast, diversity, and colorblind safety")
    p.add_argument("--compare", metavar="TEXT_OR_HEX",
                   help="Compare generated palette with another (text or comma-separated HEX)")
    p.add_argument("--interactive", action="store_true",
                   help="Launch interactive REPL mode for iterative palette refinement")

    # Options
    p.add_argument("--count", "-n", type=int, default=5, help="Number of colors (default: 5)")
    p.add_argument("--format", "-f", default="terminal",
                   choices=["terminal", "json", "css", "scss", "svg", "csv", "html", "png"],
                   help="Output format (default: terminal)")
    p.add_argument("--output", "-o", metavar="FILE", help="Write output to file instead of stdout")
    p.add_argument("--harmony-mode", default="complementary",
                   choices=["complementary", "analogous", "triadic", "split-complementary", "tetradic", "monochromatic"],
                   help="Harmony mode (used with --harmony)")
    p.add_argument("--prefix", default="color", help="Variable prefix for CSS/SCSS output (default: color)")
    p.add_argument("--no-info", action="store_true", help="Terminal mode: show only color blocks")
    p.add_argument("--colorblind", action="store_true",
                   help="Optimize palette for colorblind accessibility")
    p.add_argument("--colorblind-type", default="deuteranopia",
                   choices=["protanopia", "deuteranopia", "tritanopia"],
                   help="Type of color vision deficiency (default: deuteranopia)")
    p.add_argument("--tags", metavar="TAGS", help="Comma-separated tags for saved palettes")
    p.add_argument("--version", "-v", action="version", version=f"chroma-fountain {__version__}")

    return p

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Handle --interactive mode
    if args.interactive:
        interactive_mode()
        return

    # Handle --list-presets
    if args.list_presets:
        print("Available presets:")
        for name, keywords in sorted(PRESETS.items()):
            print(f"  {name:20s} — {', '.join(keywords)}")
        return

    # Handle --list-saved
    if args.list_saved:
        list_saved_palettes()
        return

    # Generate palette
    if args.load:
        colors = load_palette(args.load)
        if colors is None:
            sys.exit(1)
    elif args.image:
        colors = generate_from_image(args.image, args.count)
    elif args.random:
        colors = generate_random(args.count)
    elif args.preset:
        colors = generate_preset(args.preset, args.count)
    elif args.harmony:
        base = args.harmony
        if not base.startswith("#"):
            base = "#" + base
        colors = generate_harmony(base, args.harmony_mode)
    elif args.text:
        colors = generate_from_text(args.text, args.count)
    else:
        # Default: generate from a random seed
        colors = generate_random(args.count)

    # Apply colorblind optimization
    if args.colorblind:
        colors = make_colorblind_safe(colors, cvd_type=args.colorblind_type)

    # Save palette if requested
    if args.save:
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        save_palette(args.save, colors, tags=tags)

    # Format output
    if args.format == "terminal":
        output = format_terminal(colors, show_info=not args.no_info)
    elif args.format == "json":
        output = format_json(colors)
    elif args.format == "css":
        output = format_css(colors, args.prefix)
    elif args.format == "scss":
        output = format_scss(colors, args.prefix)
    elif args.format == "svg":
        output = format_svg(colors)
    elif args.format == "csv":
        output = format_csv(colors)
    elif args.format == "html":
        output = format_html(colors)
    elif args.format == "png":
        output = format_png(colors)
    else:
        output = format_terminal(colors)

    # Output
    if args.output:
        mode = "wb" if args.format == "png" else "w"
        with open(args.output, mode) as f:
            f.write(output)
            if mode == "w":
                f.write("\n")
        print(f"Palette saved to {args.output}", file=sys.stderr)
    else:
        if args.format == "png":
            # Can't write binary to stdout easily; warn and use terminal format
            print("Error: PNG format requires --output <file>.", file=sys.stderr)
            print("Falling back to terminal output.", file=sys.stderr)
            print(format_terminal(colors, show_info=not args.no_info))
        else:
            print(output)

    # Handle --score
    if args.score:
        print()
        print(format_score_report(colors))

    # Handle --compare
    if args.compare:
        print()
        # Determine if it's HEX colors or text
        if "," in args.compare or args.compare.startswith("#") or all(
            c in "0123456789abcdefABCDEF#" for c in args.compare.replace(",", "").replace(" ", "")
        ):
            # Parse as comma-separated HEX
            hex_strs = [h.strip() for h in args.compare.split(",")]
            hex_strs = [h if h.startswith("#") else f"#{h}" for h in hex_strs]
            compare_colors = hex_strs
        else:
            # Treat as text
            compare_colors = generate_from_text(args.compare, len(colors))
        print(compare_palettes(colors, compare_colors, "Generated", args.compare))

if __name__ == "__main__":
    main()
