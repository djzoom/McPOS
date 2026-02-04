"""
Kat 频道 Lo-Fi 曲目重命名工具

功能：
- 为 UUID 格式的文件生成 Lo-Fi 风格的标题
- 写入 ID3 标签（标题和艺术家 0xgarfield）
- 避免与现有 songs 目录中的标题重复
- 避免过度使用高频词汇
"""

from __future__ import annotations

import csv
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from ..core.logging import log_info, log_warning, log_error

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    MP3 = None  # type: ignore
    ID3 = None  # type: ignore
    TIT2 = None  # type: ignore
    TPE1 = None  # type: ignore
    TALB = None  # type: ignore


# 高频词汇（需要避免过度使用）
HIGH_FREQUENCY_WORDS = {
    "Echoes", "Dreams", "Quiet", "Neon", "Midnight", "Light", "Loops", 
    "Beneath", "Through", "The", "And", "In", "On", "Of", "Gilded",
    "Porcelain", "Whispers", "Reflections", "Shadows", "Waves"
}

# 扩大词汇库 - 首单词候选（按类别分组，确保多样性）
FIRST_WORD_CATEGORIES = {
    "颜色": [
        "Crimson", "Amber", "Emerald", "Cerulean", "Obsidian", "Bronze", 
        "Verdant", "Iridescent", "Sapphire", "Azure", "Violet", "Coral",
        "Ivory", "Ebony", "Copper", "Silver", "Gold", "Platinum", "Jade",
        "Turquoise", "Magenta", "Indigo", "Maroon", "Teal", "Lavender"
    ],
    "材质": [
        "Porcelain", "Velvet", "Silk", "Linen", "Wool", "Leather", "Brass",
        "Crystal", "Marble", "Granite", "Wooden", "Metallic", "Glassy",
        "Frosted", "Gilded", "Polished", "Rough", "Smooth", "Textured"
    ],
    "自然": [
        "Lunar", "Solar", "Stellar", "Celestial", "Terrestrial", "Aquatic",
        "Alpine", "Coastal", "Desert", "Forest", "Meadow", "Prairie",
        "Tundra", "Tropical", "Arctic", "Temperate", "Equatorial"
    ],
    "抽象": [
        "Ethereal", "Quantum", "Chromatic", "Resonant", "Luminous", "Vibrant",
        "Serene", "Tranquil", "Melodic", "Harmonic", "Rhythmic", "Temporal",
        "Spatial", "Dimensional", "Infinite", "Finite", "Abstract", "Concrete"
    ],
    "动作/状态": [
        "Fading", "Rising", "Falling", "Drifting", "Flowing", "Settling",
        "Emerging", "Dissolving", "Crystallizing", "Melting", "Freezing",
        "Evaporating", "Condensing", "Expanding", "Contracting", "Rotating"
    ],
    "数字/时间": [
        "First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh",
        "Eighth", "Ninth", "Tenth", "Eleventh", "Twelfth", "Thirteenth",
        "Midnight", "Dawn", "Dusk", "Noon", "Twilight", "Sunrise", "Sunset"
    ],
    "其他": [
        "Forgotten", "Remembered", "Lost", "Found", "Hidden", "Revealed",
        "Ancient", "Modern", "Timeless", "Ephemeral", "Eternal", "Momentary",
        "Silent", "Whispered", "Echoed", "Resonated", "Vibrated", "Pulsated"
    ]
}

# 所有首单词候选（扁平化）
ALL_FIRST_WORDS = [word for words in FIRST_WORD_CATEGORIES.values() for word in words]

# 多样化词汇（用于标题其他位置）
DIVERSE_VOCABULARY = [
    "Emerald", "Porcelain", "Iridescent", "Obsidian", "Cerulean", "Bronze", 
    "Gilded", "Verdant", "Frozen", "Submerged", "Terra", "Cotta", "Lunar", 
    "Auric", "Chromatic", "Ethereal", "Quantum", "Crystalline", "Forgotten",
    "Glimmering", "Silvered", "Fading", "Resonant", "Lumina", "Solar", 
    "Veiled", "Steampunk", "Biotic", "Whispers", "Reflections", "Shadows",
    "Waves", "Tides", "Currents", "Breezes", "Gusts", "Zephyrs", "Gales",
    "Haze", "Mist", "Fog", "Dew", "Frost", "Ice", "Snow", "Rain", "Drizzle",
    "Streets", "Avenues", "Boulevards", "Lanes", "Paths", "Trails", "Routes",
    "Horizons", "Skies", "Clouds", "Stars", "Moons", "Suns", "Planets"
]


def load_existing_titles(songs_dir: Path) -> Set[str]:
    """
    从 songs 目录加载所有现有标题（用于去重）
    
    Args:
        songs_dir: songs 目录路径
    
    Returns:
        现有标题集合（小写，用于比较）
    """
    existing_titles: Set[str] = set()
    
    if not songs_dir.exists():
        log_warning(f"songs 目录不存在: {songs_dir}")
        return existing_titles
    
    for mp3_file in songs_dir.glob("*.mp3"):
        # 提取标题（文件名去掉 .mp3）
        title = mp3_file.stem
        existing_titles.add(title.lower())
    
    log_info(f"从 songs 目录加载了 {len(existing_titles)} 个现有标题")
    return existing_titles


def is_uuid_format(text: str) -> bool:
    """检测是否为UUID格式（xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx）"""
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    uuid_no_dash_pattern = r'^[0-9a-f]{32}$'
    text_lower = text.lower().replace(' ', '').replace('-', '')
    return bool(re.match(uuid_pattern, text.lower()) or re.match(uuid_no_dash_pattern, text_lower))


def calculate_title_similarity(title1: str, title2: str) -> float:
    """
    计算两个标题的相似度（参考 ai_title_generator.py）
    
    Returns:
        相似度分数 (0.0 - 1.0)
    """
    # 转换为小写并提取单词
    words1 = set(re.findall(r'\b\w+\b', title1.lower()))
    words2 = set(re.findall(r'\b\w+\b', title2.lower()))
    
    if not words1 or not words2:
        return 0.0
    
    # Jaccard 相似度
    intersection = words1 & words2
    union = words1 | words2
    jaccard = len(intersection) / len(union) if union else 0.0
    
    # LCS 相似度
    def lcs_similarity(s1: str, s2: str) -> float:
        s1_clean = re.sub(r'[^\w]', '', s1.lower())
        s2_clean = re.sub(r'[^\w]', '', s2.lower())
        
        if not s1_clean or not s2_clean:
            return 0.0
        
        m, n = len(s1_clean), len(s2_clean)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1_clean[i-1] == s2_clean[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])
        
        lcs_len = dp[m][n]
        max_len = max(m, n)
        return lcs_len / max_len if max_len > 0 else 0.0
    
    lcs_sim = lcs_similarity(title1, title2)
    
    # 组合相似度（Jaccard 0.6，LCS 0.4）
    combined_similarity = 0.6 * jaccard + 0.4 * lcs_sim
    
    return combined_similarity


def check_title_uniqueness(new_title: str, existing_titles: Set[str], threshold: float = 0.6) -> Tuple[bool, Optional[str], float]:
    """
    检查标题是否与现有标题重复
    
    Args:
        new_title: 新生成的标题
        existing_titles: 现有标题集合（小写）
        threshold: 相似度阈值（默认 0.6，即 60%）
    
    Returns:
        (是否唯一, 最相似的标题, 相似度分数)
    """
    if not existing_titles:
        return True, None, 0.0
    
    # 先检查完全重复
    if new_title.lower() in existing_titles:
        return False, new_title.lower(), 1.0
    
    # 检查相似度
    max_similarity = 0.0
    most_similar_title = None
    
    for existing_title in existing_titles:
        similarity = calculate_title_similarity(new_title, existing_title)
        if similarity > max_similarity:
            max_similarity = similarity
            most_similar_title = existing_title
    
    is_unique = max_similarity < threshold
    return is_unique, most_similar_title, max_similarity


def check_vocabulary_diversity(title: str, max_high_freq_words: int = 2) -> Tuple[bool, List[str]]:
    """
    检查标题的词汇多样性
    
    Args:
        title: 标题文本
        max_high_freq_words: 允许的最大高频词数量
    
    Returns:
        (是否通过检查, 发现的高频词列表)
    """
    words = re.findall(r'\b\w+\b', title)
    found_high_freq = [w for w in words if w in HIGH_FREQUENCY_WORDS]
    
    is_diverse = len(found_high_freq) <= max_high_freq_words
    return is_diverse, found_high_freq


def build_title_templates(songs_dir: Path) -> List[str]:
    """
    从 songs 目录分析标题模式，构建模板库
    
    Returns:
        标题模板列表（可用于生成新标题）
    """
    templates = []
    
    if not songs_dir.exists():
        return templates
    
    # 从现有标题中提取模式
    for mp3_file in songs_dir.glob("*.mp3"):
        title = mp3_file.stem
        templates.append(title)
    
    return templates


def generate_title_from_template(
    templates: List[str],
    diversity_tracker: DiversityTracker,
    existing_titles: Set[str],
    target_length: Optional[int] = None,
    preferred_first_words: Optional[List[str]] = None,
) -> Optional[str]:
    """
    从模板库生成标题（不消耗 API Token）
    
    Args:
        templates: 标题模板列表
        diversity_tracker: 多样性跟踪器
        existing_titles: 现有标题集合
        target_length: 目标长度
        preferred_first_words: 优先使用的首单词
    
    Returns:
        生成的标题，如果无法生成则返回 None
    """
    if not templates:
        return None
    
    # Hard cap to prevent runaway generation cost/time.
    max_attempts = 2  # 尝试从模板生成
    
    for attempt in range(max_attempts):
        # 随机选择一个模板
        template = random.choice(templates)
        template_words = template.split()
        
        if not template_words:
            continue
        
        # 如果指定了目标长度，尝试调整
        if target_length and len(template_words) != target_length:
            # 尝试通过添加/删除单词来调整长度
            if len(template_words) < target_length:
                # 添加单词
                additional_words = random.sample(DIVERSE_VOCABULARY, min(target_length - len(template_words), 3))
                new_words = template_words + additional_words
            else:
                # 删除单词（保留前几个）
                new_words = template_words[:target_length]
        else:
            new_words = template_words
        
        # 如果指定了优先首单词，尝试替换首单词
        if preferred_first_words and new_words:
            # 50% 概率替换首单词
            if random.random() < 0.5:
                new_first_word = random.choice(preferred_first_words)
                new_words[0] = new_first_word
        
        # 组合新标题
        new_title = " ".join(new_words)
        
        # 检查唯一性
        if new_title.lower() in existing_titles:
            continue
        
        # 检查相似度
        is_unique, _, similarity = check_title_uniqueness(new_title, existing_titles, threshold=0.6)
        if not is_unique:
            continue
        
        # 检查词汇多样性
        is_diverse, _ = check_vocabulary_diversity(new_title, max_high_freq_words=2)
        if not is_diverse:
            continue
        
        return new_title
    
    return None


class DiversityTracker:
    """跟踪已生成标题的多样性指标"""
    
    def __init__(self):
        self.first_words: Counter[str] = Counter()
        self.lengths: Counter[int] = Counter()
        self.all_words: Counter[str] = Counter()
        self.used_titles: Set[str] = set()
    
    def add_title(self, title: str):
        """添加一个标题到跟踪器"""
        words = title.split()
        if words:
            self.first_words[words[0]] += 1
        self.lengths[len(words)] += 1
        for word in words:
            self.all_words[word.lower()] += 1
        self.used_titles.add(title.lower())
    
    def get_least_used_first_words(self, count: int = 20) -> List[str]:
        """获取使用次数最少的首单词"""
        if not self.first_words:
            return random.sample(ALL_FIRST_WORDS, min(count, len(ALL_FIRST_WORDS)))
        
        # 获取所有可能的首单词
        all_possible = set(ALL_FIRST_WORDS)
        used = set(self.first_words.keys())
        unused = list(all_possible - used)
        
        # 如果未使用的单词足够，返回它们
        if len(unused) >= count:
            return random.sample(unused, count)
        
        # 否则返回使用次数最少的单词
        least_used = sorted(self.first_words.items(), key=lambda x: x[1])[:count]
        return [word for word, _ in least_used]
    
    def get_target_length(self, total_needed: int) -> int:
        """根据目标分布返回应该使用的标题长度"""
        # 目标分布：2词(10%), 3词(20%), 4词(30%), 5词(30%), 6词(10%)
        target_dist = {2: 0.10, 3: 0.20, 4: 0.30, 5: 0.30, 6: 0.10}
        
        # 计算当前分布
        current_total = sum(self.lengths.values())
        if current_total == 0:
            # 第一个标题，随机选择一个长度
            return random.choices([2, 3, 4, 5, 6], weights=[10, 20, 30, 30, 10])[0]
        
        # 计算每个长度的目标数量和当前数量
        length_scores = {}
        for length, target_pct in target_dist.items():
            target_count = int(total_needed * target_pct)
            current_count = self.lengths.get(length, 0)
            deficit = target_count - current_count
            length_scores[length] = deficit
        
        # 返回赤字最大的长度
        return max(length_scores.items(), key=lambda x: x[1])[0]
    
    def get_diversity_stats(self) -> Dict:
        """获取多样性统计"""
        return {
            "unique_first_words": len(self.first_words),
            "first_word_repeat_rate": (sum(self.first_words.values()) - len(self.first_words)) / max(sum(self.first_words.values()), 1) * 100,
            "length_distribution": dict(self.lengths),
            "top_first_words": dict(self.first_words.most_common(10)),
            "top_words": dict(self.all_words.most_common(20))
        }


def generate_lofi_title_api(
    client: OpenAI,
    model: str,
    existing_titles: Set[str],
    diversity_tracker: Optional[DiversityTracker] = None,
    target_length: Optional[int] = None,
    preferred_first_words: Optional[List[str]] = None,
    attempt: int = 1,
) -> Optional[str]:
    """
    使用 OpenAI API 生成 Lo-Fi 风格的标题（增强多样性控制）
    
    Args:
        client: OpenAI 客户端
        model: 模型名称
        existing_titles: 现有标题集合（用于避免重复）
        diversity_tracker: 多样性跟踪器
        target_length: 目标标题长度（词数）
        preferred_first_words: 优先使用的首单词列表
        attempt: 尝试次数（用于重试）
    
    Returns:
        生成的标题，如果失败返回 None
    """
    # 构建现有标题列表（用于 prompt）
    existing_titles_list = list(existing_titles)[:50]  # 限制数量，避免 prompt 过长
    existing_titles_str = "\n".join([f"- {title}" for title in existing_titles_list])
    
    # 构建首单词多样性提示
    first_word_hint = ""
    if preferred_first_words:
        first_word_hint = f"\n**First Word Diversity (CRITICAL):**\n"
        first_word_hint += f"- STRONGLY prefer starting with one of these underused words: {', '.join(preferred_first_words[:15])}\n"
        first_word_hint += f"- AVOID starting with words that have been used many times already\n"
        first_word_hint += f"- This is critical for maintaining title diversity\n"
    
    # 构建长度提示
    length_hint = ""
    if target_length:
        length_hint = f"\n**Title Length (CRITICAL):**\n"
        length_hint += f"- Generate a title with EXACTLY {target_length} words\n"
        length_hint += f"- This is critical for maintaining length diversity\n"
    
    # 构建已使用首单词警告
    used_first_words_hint = ""
    if diversity_tracker and diversity_tracker.first_words:
        top_used = [word for word, _ in diversity_tracker.first_words.most_common(10)]
        used_first_words_hint = f"\n**AVOID these overused first words:** {', '.join(top_used)}\n"
    
    prompt = f"""You are a creative director for Kat Records, a virtual vinyl label specializing in Lo-Fi Jazz-Hop music.

Generate a poetic, evocative track title for a Lo-Fi instrumental piece.

**Style Guidelines:**
- Poetic, atmospheric, literary
- Title case (e.g., "Above the Skyline Below the Noise")
- Lo-Fi aesthetic: calm, cinematic, quietly human
{length_hint}
{first_word_hint}
{used_first_words_hint}
**Vocabulary Requirements:**
- AVOID overused words: Echoes, Dreams, Quiet, Neon, Midnight, Light, Loops, Beneath, Through, Gilded, Porcelain, Whispers, Reflections, Shadows, Waves
- USE diverse vocabulary from these categories:
  * Colors: Crimson, Amber, Emerald, Cerulean, Obsidian, Bronze, Verdant, Iridescent, Sapphire, Azure, Violet, Coral, Ivory, Ebony, Copper, Silver, Gold, Platinum, Jade, Turquoise, Magenta, Indigo, Maroon, Teal, Lavender
  * Materials: Porcelain, Velvet, Silk, Linen, Wool, Leather, Brass, Crystal, Marble, Granite, Wooden, Metallic, Glassy, Frosted, Polished, Rough, Smooth, Textured
  * Nature: Lunar, Solar, Stellar, Celestial, Terrestrial, Aquatic, Alpine, Coastal, Desert, Forest, Meadow, Prairie, Tundra, Tropical, Arctic, Temperate
  * Abstract: Ethereal, Quantum, Chromatic, Resonant, Luminous, Vibrant, Serene, Tranquil, Melodic, Harmonic, Rhythmic, Temporal, Spatial, Dimensional, Infinite, Abstract
  * Actions: Fading, Rising, Falling, Drifting, Flowing, Settling, Emerging, Dissolving, Crystallizing, Melting, Freezing, Evaporating, Condensing, Expanding, Contracting, Rotating
- CREATE unique combinations: Mix unexpected words from different categories
- Vary sentence structures: Some titles can start with articles (A, An, The), numbers, or descriptive words

**Uniqueness Requirements:**
- Must be unique and different from these existing titles:
{existing_titles_str}
- Avoid similar patterns, imagery, or word combinations
- If a title is too similar to an existing one (>60% similarity), it will be rejected

**Examples of Good Titles (showing diversity):**
- "305 Sunset Snare" (number + location + instrument)
- "6th Street Soft Kick" (number + location + description + instrument)
- "99% Rain" (number + weather)
- "A Jar Half Full of Melody" (article + object + description + abstract)
- "Above the Skyline Below the Noise" (preposition + location + preposition + abstract)
- "Afternoons in Goldenrod Light" (time + preposition + color + noun)
- "Alpine Bells Beneath the First Light" (location + object + preposition + time)
- "Amber Horizons Woven Through Whispering Pines" (color + abstract + verb + description + nature)

**Critical:**
- Return ONLY the title, no quotes, no explanations, no extra text
- Do NOT include artist name or any suffix
- Do NOT use "LP", "Vinyl", "Session" or similar terms
- Title should be a complete, standalone phrase
- Ensure the first word is from the preferred list if provided
- Ensure the title has the exact number of words specified if provided

Generate a unique, creative Lo-Fi track title now:"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative director for Kat Records, a virtual vinyl label. You create poetic, evocative track titles that capture emotions and fleeting moments through sound. Your titles are literary, refined, and timeless. You prioritize diversity in first words, title lengths, and vocabulary to ensure each track feels unique."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.9,  # 提高温度以增加多样性
            max_tokens=40,
        )
        
        content = response.choices[0].message.content
        if not content:
            return None
        
        new_title = content.strip()
        new_title = new_title.strip('"').strip("'").strip()
        
        if not new_title:
            return None
        
        # 确保首字母大写
        if len(new_title) > 1:
            new_title = new_title[0].upper() + new_title[1:]
        
        # 验证长度（如果指定了目标长度）
        if target_length:
            word_count = len(new_title.split())
            if word_count != target_length:
                # 如果长度不匹配，尝试调整（但这不是完美的解决方案）
                # 这里我们只是记录警告，让调用者决定是否重试
                pass
        
        return new_title
        
    except Exception as e:
        log_error(f"API 调用失败 (尝试 {attempt}): {e}")
        return None


def write_id3_tags(file_path: Path, title: str, artist: str = "0xgarfield", album: Optional[str] = None) -> bool:
    """
    写入 ID3 标签到 MP3 文件
    
    Args:
        file_path: MP3 文件路径
        title: 标题
        artist: 艺术家（默认 "0xgarfield"）
        album: 专辑名称（可选）
    
    Returns:
        是否成功
    """
    if not MUTAGEN_AVAILABLE or MP3 is None or ID3 is None or TIT2 is None or TPE1 is None:
        log_error("mutagen 不可用，无法写入 ID3 标签")
        return False
    
    try:
        audio = MP3(str(file_path), ID3=ID3)
        
        # 如果没有 ID3 标签，创建
        if audio.tags is None:
            audio.add_tags()
        
        # 写入标题 (TIT2)
        if TIT2 is not None:
            audio.tags.setall("TIT2", [TIT2(encoding=3, text=title)])
        
        # 写入艺术家 (TPE1)
        if TPE1 is not None:
            audio.tags.setall("TPE1", [TPE1(encoding=3, text=artist)])
        
        # 写入专辑 (TALB) - 可选
        if album and TALB is not None:
            audio.tags.setall("TALB", [TALB(encoding=3, text=album)])
        
        audio.save()
        return True
        
    except Exception as e:
        log_error(f"ID3 写入失败: {file_path.name} - {e}")
        return False


def rename_kat_lofi_library(
    channel_id: str,
    channels_root: Path,
    source_dir: str = "Suno 0127",
    model: str = "gpt-4o-mini",
    execute: bool = False,
    use_api: bool = True,
    rename_all: bool = False,
) -> None:
    """
    重命名 Kat 频道的 Lo-Fi 曲目库
    
    Args:
        channel_id: 频道 ID（"kat"）
        channels_root: 频道根目录
        source_dir: 源目录名称（相对于 library/）
        model: OpenAI 模型名称
        execute: 是否执行实际重命名
        use_api: 是否使用 API 生成标题
        rename_all: 是否重新命名所有文件（不仅仅是 UUID 格式）
    """
    songs_dir = channels_root / channel_id / "library" / "songs"
    source_path = channels_root / channel_id / "library" / source_dir
    
    if not source_path.exists():
        raise ValueError(f"源目录不存在: {source_path}")
    
    if not songs_dir.exists():
        log_warning(f"songs 目录不存在: {songs_dir}，将无法进行去重检查")
    
    # 加载现有标题
    existing_titles = load_existing_titles(songs_dir)
    
    # 构建模板库（用于减少 API 调用）
    templates = build_title_templates(songs_dir)
    log_info(f"从 songs 目录加载了 {len(templates)} 个标题模板")
    
    # 初始化 API 客户端
    client = None
    if use_api:
        if not OPENAI_AVAILABLE:
            log_warning("OpenAI 不可用，将无法使用 API 生成标题")
            use_api = False
        else:
            api_key_path = Path("config/openai_api_key.txt")
            if api_key_path.exists():
                api_key = api_key_path.read_text().strip()
            else:
                api_key = os.getenv("OPENAI_API_KEY")
            
            if api_key:
                client = OpenAI(api_key=api_key)
            else:
                log_warning("未找到 OpenAI API Key，将无法使用 API 生成标题")
                use_api = False
    
    # 查找所有 MP3 文件
    all_mp3_files = list(source_path.glob("*.mp3"))
    
    if rename_all:
        # 重新命名所有文件
        files_to_process = all_mp3_files
        log_info(f"⚠️  重新命名模式：将重新命名所有 {len(files_to_process)} 个文件以增加多样性")
    else:
        # 只处理 UUID 格式的文件
        files_to_process = [f for f in all_mp3_files if is_uuid_format(f.stem)]
    
    if not files_to_process:
        log_info(f"源目录中没有需要重命名的文件")
        return
    
    log_info(f"频道: {channel_id}")
    log_info(f"源目录: {source_path}")
    log_info(f"总 MP3 文件数: {len(all_mp3_files)}")
    log_info(f"需要重命名的文件: {len(files_to_process)} 个")
    log_info(f"现有标题数: {len(existing_titles)} 个")
    log_info("")
    
    if execute:
        log_info("⚠️  执行模式：将真正重命名文件和写入 ID3 标签")
    else:
        log_info("⚠️  DRY-RUN 模式：不会真正重命名文件")
        log_info(f"⚠️  注意：DRY-RUN 模式下仍会调用 API 生成标题（用于预览）")
        log_info(f"⚠️  建议：先处理少量文件测试，确认效果后再执行全部")
    log_info("")
    
    # 初始化多样性跟踪器
    diversity_tracker = DiversityTracker()
    
    # 初始化
    plan = []
    used_titles: Set[str] = set()
    success_count = 0
    error_count = 0
    skipped_count = 0
    api_call_count = 0
    
    # 处理每个文件
    for idx, file_path in enumerate(files_to_process, 1):
        filename = file_path.name
        
        # 获取多样性提示
        target_length = diversity_tracker.get_target_length(len(files_to_process))
        preferred_first_words = diversity_tracker.get_least_used_first_words(20)
        
        # 生成标题
        new_title: Optional[str] = None
        # Hard cap to prevent runaway OpenAI usage.
        max_attempts = 2
        
        # 策略：优先使用模板库（不消耗 API），如果模板库无法生成合适的标题，再使用 API
        use_template_first = True
        template_attempts = 0
        max_template_attempts = 20  # 模板库尝试次数
        
        for attempt in range(1, max_attempts + 1):
            # 优先尝试模板库（前几次尝试）
            if use_template_first and templates and template_attempts < max_template_attempts:
                template_attempts += 1
                new_title = generate_title_from_template(
                    templates,
                    diversity_tracker,
                    existing_titles | used_titles,
                    target_length=target_length,
                    preferred_first_words=preferred_first_words
                )
                if new_title:
                    # 模板库成功生成，跳过 API 调用
                    break
                # 如果模板库失败，继续尝试 API
                if template_attempts >= max_template_attempts:
                    use_template_first = False  # 模板库用尽，切换到 API
            
            # 使用 API 生成
            if use_api and client:
                new_title = generate_lofi_title_api(
                    client, 
                    model, 
                    existing_titles | used_titles,
                    diversity_tracker=diversity_tracker,
                    target_length=target_length,
                    preferred_first_words=preferred_first_words,
                    attempt=attempt
                )
                api_call_count += 1
            elif not use_api:
                log_error("API 不可用，无法生成标题")
                break
            
            if not new_title:
                continue
            
            # 检查唯一性
            is_unique, similar_title, similarity = check_title_uniqueness(
                new_title, existing_titles | used_titles, threshold=0.6
            )
            
            if not is_unique:
                if attempt <= 3:  # 前3次尝试才显示警告
                    log_warning(f"  尝试 {attempt}: 标题 '{new_title}' 与 '{similar_title}' 相似度 {similarity:.1%}，重新生成...")
                new_title = None
                continue
            
            # 检查词汇多样性
            is_diverse, high_freq_words = check_vocabulary_diversity(new_title, max_high_freq_words=2)
            
            if not is_diverse:
                if attempt <= 3:
                    log_warning(f"  尝试 {attempt}: 标题 '{new_title}' 包含过多高频词: {high_freq_words}，重新生成...")
                new_title = None
                continue
            
            # 检查首单词多样性（如果已使用超过10次，建议避免）
            words = new_title.split()
            if words:
                first_word = words[0]
                if diversity_tracker.first_words[first_word] >= 10:
                    if attempt <= 5:  # 前5次尝试可以接受，之后强制要求多样性
                        pass  # 允许继续
                    else:
                        if attempt <= 6:
                            log_warning(f"  尝试 {attempt}: 首单词 '{first_word}' 已使用 {diversity_tracker.first_words[first_word]} 次，尝试使用其他首单词...")
                        new_title = None
                        continue
            
            # 通过所有检查
            break
        
        if not new_title:
            log_error(f"[{idx}/{len(files_to_process)}] ❌ 无法生成有效标题: {filename}")
            error_count += 1
            continue
        
        used_titles.add(new_title.lower())
        diversity_tracker.add_title(new_title)  # 添加到跟踪器
        
        # 生成新文件名（纯标题）
        new_filename = f"{new_title}.mp3"
        new_path = source_path / new_filename
        
        # 检查目标文件是否已存在
        if new_path.exists() and file_path != new_path:
            log_warning(f"[{idx}/{len(files_to_process)}] ⚠️  目标文件已存在: {new_filename}")
            skipped_count += 1
            continue
        
        plan.append((filename, new_filename, new_title, "0xgarfield"))
        
        if execute:
            try:
                # 写入 ID3 标签
                id3_success = write_id3_tags(file_path, new_title, artist="0xgarfield")
                if not id3_success:
                    log_warning(f"  ID3 标签写入失败，但继续重命名文件")
                
                # 重命名文件
                file_path.rename(new_path)
                success_count += 1
                
                if idx % 50 == 0 or idx == len(files_to_process):
                    log_info(f"[{idx}/{len(files_to_process)}] ✅ {filename} -> {new_filename}")
            except Exception as exc:
                log_error(f"[{idx}/{len(files_to_process)}] ❌ 失败: {filename} -> {new_filename} ({exc})")
                error_count += 1
        else:
            if idx % 50 == 0 or idx == len(files_to_process):
                log_info(f"[{idx}/{len(files_to_process)}] 📝 {filename} -> {new_filename}")
    
    # 写入 CSV 计划
    output_csv = source_path / "rename_plan.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["old", "new", "title", "artist"])
        for old, new, title, artist in plan:
            writer.writerow([old, new, title, artist])
    
    log_info("")
    log_info(f"✅ 计划已写入: {output_csv}")
    log_info(f"   共 {len(plan)} 个文件")
    if execute:
        log_info(f"   成功: {success_count}, 失败: {error_count}, 跳过: {skipped_count}")
    
    # 输出多样性统计
    if diversity_tracker.used_titles:
        stats = diversity_tracker.get_diversity_stats()
        log_info("")
        log_info("=== 多样性统计 ===")
        log_info(f"唯一首单词数: {stats['unique_first_words']}")
        log_info(f"首单词重复率: {stats['first_word_repeat_rate']:.1f}%")
        log_info(f"标题长度分布: {stats['length_distribution']}")
        log_info(f"API 调用次数: {api_call_count}")
        log_info("")
        log_info("Top 10 首单词:")
        for word, count in list(stats['top_first_words'].items())[:10]:
            log_info(f"  {word}: {count} 次")


def is_problematic_title(title: str) -> Tuple[bool, str]:
    """
    检查标题是否有问题（语法错误、不完整等）
    
    Returns:
        (是否有问题, 问题类型)
    """
    # 检查问号
    if '？' in title or '?' in title:
        return True, "包含问号"
    
    # 检查以介词/冠词结尾（可能不完整）
    if title.endswith((' on', ' in', ' of', ' at', ' to', ' for', ' with', ' by', ' from', ' and', ' a', ' an', ' the')):
        return True, "以介词/冠词结尾"
    
    # 检查以连词结尾
    if title.endswith((' and', ' or', ' but')):
        return True, "以连词结尾"
    
    # 检查标题太短（少于2个词）
    if len(title.split()) < 2:
        return True, "标题太短"
    
    # 检查标题过长（超过8个词，可能是错误）
    if len(title.split()) > 8:
        return True, "标题过长"
    
    return False, ""


def fix_problematic_title_api(
    client: OpenAI,
    model: str,
    problematic_title: str,
    existing_titles: Set[str],
    diversity_tracker: Optional[DiversityTracker] = None,
    attempt: int = 1,
) -> Optional[str]:
    """
    使用 API 修复有问题的标题
    
    Args:
        client: OpenAI 客户端
        model: 模型名称
        problematic_title: 有问题的标题
        existing_titles: 现有标题集合
        diversity_tracker: 多样性跟踪器
        attempt: 尝试次数
    
    Returns:
        修复后的标题，如果失败返回 None
    """
    # 构建现有标题列表
    existing_titles_list = list(existing_titles)[:50]
    existing_titles_str = "\n".join([f"- {title}" for title in existing_titles_list])
    
    # 获取多样性提示
    preferred_first_words = []
    if diversity_tracker:
        preferred_first_words = diversity_tracker.get_least_used_first_words(15)
    
    first_word_hint = ""
    if preferred_first_words:
        first_word_hint = f"\n**First Word Diversity:**\n"
        first_word_hint += f"- Prefer starting with one of these underused words: {', '.join(preferred_first_words[:10])}\n"
    
    prompt = f"""You are a creative director for Kat Records, a virtual vinyl label specializing in Lo-Fi Jazz-Hop music.

I have a problematic track title that needs to be fixed. The current title is incomplete or grammatically incorrect:

**Current Title (PROBLEMATIC):** "{problematic_title}"

**Task:**
Fix this title to make it complete, grammatically correct, and poetic. The title should:
1. Be a complete, standalone phrase (NOT ending with prepositions, articles, or conjunctions)
2. Be grammatically correct
3. Maintain the Lo-Fi aesthetic: poetic, atmospheric, literary
4. Be 2-6 words (preferably 3-5 words)
5. Be unique and different from existing titles
6. Use Title case

**Style Guidelines:**
- Poetic, atmospheric, literary
- Lo-Fi aesthetic: calm, cinematic, quietly human
- Avoid overused words: Echoes, Dreams, Quiet, Neon, Midnight, Light, Loops, Gilded, Porcelain, Whispers, Reflections, Shadows, Waves
- Use diverse vocabulary from colors, materials, nature, abstract concepts, actions
{first_word_hint}
**Uniqueness Requirements:**
- Must be unique and different from these existing titles:
{existing_titles_str}
- Avoid similar patterns or word combinations

**Examples of Good Titles:**
- "305 Sunset Snare"
- "6th Street Soft Kick"
- "99% Rain"
- "A Jar Half Full of Melody"
- "Above the Skyline Below the Noise"
- "Afternoons in Goldenrod Light"
- "Alpine Bells Beneath the First Light"

**Critical:**
- Return ONLY the fixed title, no quotes, no explanations, no extra text
- The title MUST be complete and grammatically correct
- Do NOT end with prepositions (on, in, of, at, to, for, with, by, from)
- Do NOT end with articles (a, an, the)
- Do NOT end with conjunctions (and, or, but)
- The title should be a complete, standalone phrase

Fix the problematic title now:"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a creative director for Kat Records. You fix incomplete or grammatically incorrect track titles, making them complete, poetic, and grammatically correct while maintaining the Lo-Fi aesthetic."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=40,
        )
        
        content = response.choices[0].message.content
        if not content:
            return None
        
        fixed_title = content.strip()
        fixed_title = fixed_title.strip('"').strip("'").strip()
        
        if not fixed_title:
            return None
        
        # 确保首字母大写
        if len(fixed_title) > 1:
            fixed_title = fixed_title[0].upper() + fixed_title[1:]
        
        # 验证修复后的标题不再有问题
        is_problem, problem_type = is_problematic_title(fixed_title)
        if is_problem:
            log_warning(f"  修复后的标题仍有问题 ({problem_type}): {fixed_title}")
            return None
        
        return fixed_title
        
    except Exception as e:
        log_error(f"API 调用失败 (尝试 {attempt}): {e}")
        return None


def fix_problematic_titles(
    channel_id: str,
    channels_root: Path,
    source_dir: str = "Suno 0127",
    model: str = "gpt-4o-mini",
    execute: bool = False,
) -> None:
    """
    修复有问题的标题
    
    Args:
        channel_id: 频道 ID
        channels_root: 频道根目录
        source_dir: 源目录名称
        model: OpenAI 模型名称
        execute: 是否执行实际修复
    """
    songs_dir = channels_root / channel_id / "library" / "songs"
    source_path = channels_root / channel_id / "library" / source_dir
    
    if not source_path.exists():
        raise ValueError(f"源目录不存在: {source_path}")
    
    # 加载现有标题
    existing_titles = load_existing_titles(songs_dir)
    
    # 初始化 API 客户端
    api_key_path = Path("config/openai_api_key.txt")
    if api_key_path.exists():
        api_key = api_key_path.read_text().strip()
    else:
        api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("未找到 OpenAI API Key")
    
    client = OpenAI(api_key=api_key)
    
    # 查找所有 MP3 文件
    all_mp3_files = list(source_path.glob("*.mp3"))
    
    # 检查每个文件的标题
    problematic_files = []
    for file_path in all_mp3_files:
        title = file_path.stem
        is_problem, problem_type = is_problematic_title(title)
        if is_problem:
            problematic_files.append((file_path, title, problem_type))
    
    if not problematic_files:
        log_info("✅ 没有发现有问题标题")
        return
    
    log_info(f"发现 {len(problematic_files)} 个有问题的标题")
    log_info("")
    
    if execute:
        log_info("⚠️  执行模式：将真正修复标题并重命名文件")
    else:
        log_info("⚠️  DRY-RUN 模式：不会真正修复文件")
    log_info("")
    
    # 初始化多样性跟踪器（用于修复后的标题）
    diversity_tracker = DiversityTracker()
    # 加载已存在的标题到跟踪器
    for file_path in all_mp3_files:
        title = file_path.stem
        if not is_problematic_title(title)[0]:  # 只添加正常的标题
            diversity_tracker.add_title(title)
    
    # 修复每个有问题的标题
    plan = []
    success_count = 0
    error_count = 0
    
    for idx, (file_path, old_title, problem_type) in enumerate(problematic_files, 1):
        log_info(f"[{idx}/{len(problematic_files)}] 修复: {old_title} ({problem_type})")
        
        # 使用 API 修复标题
        fixed_title: Optional[str] = None
        # Hard cap to prevent runaway OpenAI usage.
        max_attempts = 2
        
        for attempt in range(1, max_attempts + 1):
            fixed_title = fix_problematic_title_api(
                client,
                model,
                old_title,
                existing_titles | diversity_tracker.used_titles,
                diversity_tracker=diversity_tracker,
                attempt=attempt
            )
            
            if not fixed_title:
                continue
            
            # 检查唯一性
            is_unique, similar_title, similarity = check_title_uniqueness(
                fixed_title, existing_titles | diversity_tracker.used_titles, threshold=0.6
            )
            
            if not is_unique:
                if attempt <= 3:
                    log_warning(f"  尝试 {attempt}: 修复后的标题 '{fixed_title}' 与 '{similar_title}' 相似度 {similarity:.1%}，重新生成...")
                fixed_title = None
                continue
            
            # 检查词汇多样性
            is_diverse, high_freq_words = check_vocabulary_diversity(fixed_title, max_high_freq_words=2)
            
            if not is_diverse:
                if attempt <= 3:
                    log_warning(f"  尝试 {attempt}: 修复后的标题 '{fixed_title}' 包含过多高频词: {high_freq_words}，重新生成...")
                fixed_title = None
                continue
            
            # 再次验证修复后的标题没有问题
            is_problem, _ = is_problematic_title(fixed_title)
            if is_problem:
                if attempt <= 3:
                    log_warning(f"  尝试 {attempt}: 修复后的标题仍有问题，重新生成...")
                fixed_title = None
                continue
            
            # 通过所有检查
            break
        
        if not fixed_title:
            log_error(f"  ❌ 无法修复标题: {old_title}")
            error_count += 1
            continue
        
        # 添加到跟踪器
        diversity_tracker.add_title(fixed_title)
        
        # 生成新文件名
        new_filename = f"{fixed_title}.mp3"
        new_path = source_path / new_filename
        
        # 检查目标文件是否已存在
        if new_path.exists() and file_path != new_path:
            log_warning(f"  ⚠️  目标文件已存在: {new_filename}")
            error_count += 1
            continue
        
        plan.append((file_path.name, new_filename, old_title, fixed_title, "0xgarfield"))
        
        if execute:
            try:
                # 写入 ID3 标签
                id3_success = write_id3_tags(file_path, fixed_title, artist="0xgarfield")
                if not id3_success:
                    log_warning(f"  ID3 标签写入失败，但继续重命名文件")
                
                # 重命名文件
                file_path.rename(new_path)
                success_count += 1
                log_info(f"  ✅ {old_title} -> {fixed_title}")
            except Exception as exc:
                log_error(f"  ❌ 失败: {old_title} -> {fixed_title} ({exc})")
                error_count += 1
        else:
            log_info(f"  📝 {old_title} -> {fixed_title}")
    
    # 写入 CSV 计划
    output_csv = source_path / "fix_problematic_titles_plan.csv"
    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["old_filename", "new_filename", "old_title", "new_title", "artist"])
        for old_fn, new_fn, old_title, new_title, artist in plan:
            writer.writerow([old_fn, new_fn, old_title, new_title, artist])
    
    log_info("")
    log_info(f"✅ 修复计划已写入: {output_csv}")
    log_info(f"   共 {len(plan)} 个文件")
    if execute:
        log_info(f"   成功: {success_count}, 失败: {error_count}")
