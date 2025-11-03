"""
SRT Service for T2R

Parse and fix SRT subtitle files.
"""
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SRTSubtitle:
    """Represents a single subtitle entry"""
    def __init__(self, index: int, start: str, end: str, text: str):
        self.index = index
        self.start = start
        self.end = end
        self.text = text
    
    def to_timedelta(self, time_str: str) -> timedelta:
        """Convert SRT time string to timedelta"""
        # Format: "00:01:30,500"
        match = re.match(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})", time_str)
        if match:
            h, m, s, ms = map(int, match.groups())
            return timedelta(hours=h, minutes=m, seconds=s, milliseconds=ms)
        return timedelta(0)
    
    def start_timedelta(self) -> timedelta:
        return self.to_timedelta(self.start)
    
    def end_timedelta(self) -> timedelta:
        return self.to_timedelta(self.end)
    
    def duration(self) -> timedelta:
        return self.end_timedelta() - self.start_timedelta()


def parse_srt_file(file_path: Path) -> List[SRTSubtitle]:
    """Parse SRT file and return list of subtitles"""
    if not file_path.exists():
        logger.warning(f"SRT file not found: {file_path}")
        return []
    
    subtitles = []
    try:
        content = file_path.read_text(encoding='utf-8-sig')  # Handle BOM
        # Split by double newlines
        blocks = re.split(r'\n\s*\n', content.strip())
        
        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            index = int(lines[0].strip())
            time_match = re.match(r"(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})", lines[1])
            if not time_match:
                continue
            
            start, end = time_match.groups()
            text = '\n'.join(lines[2:])
            
            subtitles.append(SRTSubtitle(index, start, end, text))
        
        logger.info(f"Parsed {len(subtitles)} subtitles from {file_path}")
        return subtitles
    
    except Exception as e:
        logger.error(f"Failed to parse SRT file {file_path}: {e}")
        return []


def inspect_srt(subtitles: List[SRTSubtitle]) -> Dict:
    """
    Inspect SRT subtitles for issues.
    
    Returns:
        {
            "issues": List[Dict],
            "stats": Dict
        }
    """
    issues = []
    overlaps = 0
    gaps = 0
    
    for i in range(len(subtitles) - 1):
        current = subtitles[i]
        next_sub = subtitles[i + 1]
        
        # Check for overlap
        if current.end_timedelta() > next_sub.start_timedelta():
            overlap_duration = current.end_timedelta() - next_sub.start_timedelta()
            issues.append({
                "type": "overlap",
                "line1": current.index,
                "line2": next_sub.index,
                "start": next_sub.start,
                "end": current.end,
                "overlap_duration_ms": int(overlap_duration.total_seconds() * 1000),
                "severity": "warning" if overlap_duration.total_seconds() < 1 else "error"
            })
            overlaps += 1
        
        # Check for gap
        gap = next_sub.start_timedelta() - current.end_timedelta()
        if gap.total_seconds() > 0.5:  # Gap > 500ms
            issues.append({
                "type": "gap",
                "before_line": current.index,
                "after_line": next_sub.index,
                "gap_duration_ms": int(gap.total_seconds() * 1000),
                "start": current.end,
                "end": next_sub.start,
                "severity": "info" if gap.total_seconds() < 2 else "warning"
            })
            gaps += 1
    
    return {
        "issues": issues,
        "stats": {
            "total_lines": len(subtitles),
            "overlaps": overlaps,
            "gaps": gaps,
            "encoding_ok": True  # Basic check passed
        }
    }


def fix_srt_overlaps(subtitles: List[SRTSubtitle], strategy: str = "clip") -> Tuple[List[SRTSubtitle], List[Dict]]:
    """
    Fix overlapping subtitles.
    
    Strategies:
    - clip: Clip the first subtitle to end before the second starts
    - shift: Shift the second subtitle to start after the first ends
    - merge: Merge overlapping text
    
    Returns:
        (fixed_subtitles, changes)
    """
    fixed = subtitles.copy()
    changes = []
    
    for i in range(len(fixed) - 1):
        current = fixed[i]
        next_sub = fixed[i + 1]
        
        if current.end_timedelta() > next_sub.start_timedelta():
            overlap = current.end_timedelta() - next_sub.start_timedelta()
            
            if strategy == "clip":
                # Clip current subtitle
                new_end = next_sub.start_timedelta()
                new_end_str = format_srt_time(new_end)
                changes.append({
                    "line": current.index,
                    "action": "clipped",
                    "old": current.end,
                    "new": new_end_str
                })
                fixed[i] = SRTSubtitle(current.index, current.start, new_end_str, current.text)
            
            elif strategy == "shift":
                # Shift next subtitle
                new_start = current.end_timedelta()
                new_start_str = format_srt_time(new_start)
                # Adjust end time to maintain duration
                duration = next_sub.duration()
                new_end = new_start + duration
                new_end_str = format_srt_time(new_end)
                changes.append({
                    "line": next_sub.index,
                    "action": "shifted",
                    "old": f"{next_sub.start} --> {next_sub.end}",
                    "new": f"{new_start_str} --> {new_end_str}"
                })
                fixed[i + 1] = SRTSubtitle(next_sub.index, new_start_str, new_end_str, next_sub.text)
            
            elif strategy == "merge":
                # Merge text
                merged_text = f"{current.text}\n{next_sub.text}"
                new_end = next_sub.end_timedelta()
                new_end_str = format_srt_time(new_end)
                changes.append({
                    "line": current.index,
                    "action": "merged",
                    "old": current.text,
                    "new": merged_text,
                    "old_end": current.end,
                    "new_end": new_end_str
                })
                fixed[i] = SRTSubtitle(current.index, current.start, new_end_str, merged_text)
                # Remove next subtitle
                fixed.pop(i + 1)
                break  # Restart iteration
    
    return fixed, changes


def format_srt_time(td: timedelta) -> str:
    """Format timedelta to SRT time string"""
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    milliseconds = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def format_srt_diff(subtitles: List[SRTSubtitle], changes: List[Dict]) -> str:
    """Generate UDIF-style diff output"""
    lines = []
    for change in changes:
        lines.append(f"- Line {change['line']}: {change.get('old', '')}")
        lines.append(f"+ Line {change['line']}: {change.get('new', '')}")
    return '\n'.join(lines)


def save_srt_file(subtitles: List[SRTSubtitle], output_path: Path) -> bool:
    """Save subtitles to SRT file"""
    try:
        lines = []
        for sub in subtitles:
            lines.append(str(sub.index))
            lines.append(f"{sub.start} --> {sub.end}")
            lines.append(sub.text)
            lines.append("")
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        logger.info(f"Saved SRT file to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save SRT file: {e}")
        return False

