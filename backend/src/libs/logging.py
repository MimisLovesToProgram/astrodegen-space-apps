


def log(text: str, level: int) -> str:
    """
    Takes a string and an integer (1-10) and returns the string 
    formatted with a color gradient: Green -> Blue -> Yellow -> Red.
    """
    if not (1 <= level <= 10):
        raise ValueError("Level must be an integer between 1 and 10.")

    stops = [
        (0, 255, 0),    # Green (Level 1)
        (0, 0, 255),    # Blue  (Intermediate)
        (255, 255, 0),  # Yellow (Intermediate)
        (255, 0, 0)     # Red   (Level 10)
    ]
    
    # Scale level 1-10 across our 3 color segments (0.0 to 3.0)
    scaled = (level - 1) / 9.0 * 3.0
    seg = int(scaled)
    
    if seg >= 3:
        r, g, b = stops[3]
    else:
        t = scaled - seg  # fractional progress within the segment
        c1 = stops[seg]
        c2 = stops[seg + 1]
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)

    # Apply 24-bit ANSI foreground color escape code and reset at the end
    reset = "\033[0m"
    return f"\033[38;2;{r};{g};{b}m{text}{reset}"

# --- Example Usage ---
if __name__ == "__main__":
    for i in range(1, 11):
        print(log(f"Priority/Severity Level {i:2d}", i))
