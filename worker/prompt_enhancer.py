"""
Prompt 写实增强器 V2（针对涂抹感强化）
- 清洗所有相机/格式/色彩科学标签（11 种，全覆盖 CSV 3000 条）
- 注入强写实信号（Sony A7 IV 无反相机 + SOOC + 锐度纹理）
- 提供 negative_prompt 强力抑制油画/涂抹/塑料感

设计目标：让 Agnes Video V2.0 生成的视频"和现实分不出区别"。
"""

# ═══════════════════════════════════════════════════════
# 1. 清洗规则：CSV 里 11 种参数标签 + 变体（全覆盖）
# ═══════════════════════════════════════════════════════
ARTISTIC_TOKENS = [
    # === 色彩科学（油画感元凶）===
    "Canon Log 3", "Canon Log 2", "Canon Log",
    "S-Log3灰度模式", "S-Log3", "S-Log2", "S-Log",
    "Cinetone色彩还原", "Cinetone",
    "徕卡色彩风格", "徕卡色彩", "徕卡风格",
    "Rec.709色彩", "Rec.709",
    "LogC",
    # === 编码格式（无用）===
    "H.265 10bit录制", "H.265 10bit", "H.265",
    "H.264 10bit录制", "H.264",
    "10bit录制", "10bit",
    # === 帧率/分辨率（后端决定，prompt 里无用）===
    "4K 60fps", "4K 30fps", "4K 120fps", "4K",
    "8K 60fps", "8K 30fps", "8K",
    "60fps", "30fps", "120fps", "24fps",
    # === RAW 格式标签 ===
    "RAW格式输出后期调色", "RAW格式输出", "RAW格式",
    "R3D RAW格式记录", "R3D RAW", "R3D",
    "RAW",
    # === 电影机型号（触发"电影感"渲染）===
    "RED Monstro 8K", "RED Monstro", "RED",
    "Alexa Mini", "Alexa",
    "ARRI Alexa",
    # === 残余词 ===
    "色彩还原", "色彩风格", "灰度模式",
    "格式记录", "格式输出", "后期调色",
]

# ═══════════════════════════════════════════════════════
# 2. 写实前缀 V2（换相机 + SOOC + 锐度）
#    故意用 Sony A7 IV 无反相机，避开 ARRI/RED 电影机的艺术化倾向
# ═══════════════════════════════════════════════════════
REALISTIC_PREFIX = (
    "Ultra-detailed documentary footage, razor-sharp focus, photorealistic, "
    "shot on Sony A7 IV mirrorless camera with Sony 24-70mm f/2.8 GM lens, "
    "unedited straight out of camera, no color grading, no LUT applied, "
    "true-to-life Rec.709 color, accurate white balance 5500K, "
    "natural dynamic range. "
)

# ═══════════════════════════════════════════════════════
# 3. 写实后缀 V2（强化纹理 + 物理噪声 + 真实瑕疵）
#    油画感视频没有的：锐纹理、毛孔、发丝、传感器噪声
# ═══════════════════════════════════════════════════════
REALISTIC_SUFFIX = (
    ". Sharp textures preserved, individual hairs visible, "
    "fine surface detail, skin pores visible, micro-edge definition. "
    "Natural digital sensor noise at ISO 400, subtle grain structure. "
    "Imperfect handheld motion, subtle micro-jitter, candid unposed real moment. "
    "Documentary realism, photojournalism style. "
    "NOT a painting, NOT a 3D render, NOT digital art."
)

# ═══════════════════════════════════════════════════════
# 4. Negative prompt V2（专打涂抹感 + 塑料感 + AI 痕迹）
# ═══════════════════════════════════════════════════════
NEGATIVE_PROMPT = (
    # === 涂抹感专属（V2 新增）===
    "painterly rendering, smooth gradient, smeared details, soft edges, "
    "vaseline on lens, glossy surface, plastic sheen, "
    "CG paintover, over-rendered, hyperreal painting, digital painting, "
    "AI art artifact, beautify filter, "
    # === 绘画类 ===
    "oil painting, watercolor, acrylic, gouache, "
    "painting, brush strokes, "
    "illustration, concept art, matte painting, "
    # === 卡通 / 3D ===
    "cartoon, anime, manga, cel-shaded, "
    "3D render, CGI, Unreal Engine, Octane render, V-Ray, Blender, "
    # === 过度美化 ===
    "plastic skin, airbrushed, overly smooth skin, "
    "doll-like, porcelain, waxy, "
    # === 色彩失真 ===
    "oversaturated, HDR look, dramatic color grading, "
    "teal and orange, cinematic color cast, "
    "purple tint, green tint, "
    # === 氛围 / 梦幻 ===
    "dreamy, surreal, fantasy, magical, ethereal, "
    "glowing edges, halo effect, bloom, "
    # === 画质问题 ===
    "low detail, blurry, soft focus, out of focus, "
    "compressed, jpeg artifacts, banding"
)


def clean_prompt(raw: str) -> str:
    """去除所有参数/相机/格式标签，清理多余标点。"""
    out = raw
    for token in ARTISTIC_TOKENS:
        out = out.replace(token, "")
    # 清理连续逗号/空格
    while ",," in out:
        out = out.replace(",,", ",")
    while ", ," in out:
        out = out.replace(", ,", ",")
    while "  " in out:
        out = out.replace("  ", " ")
    return out.strip(" ,，.")


def enhance_prompt(raw: str) -> tuple[str, str]:
    """返回 (增强后 prompt, negative_prompt)。"""
    cleaned = clean_prompt(raw)
    enhanced = f"{REALISTIC_PREFIX}{cleaned}{REALISTIC_SUFFIX}"
    return enhanced, NEGATIVE_PROMPT


# ═══════════════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    samples = [
        "手持稳定器跟拍，日出云海，自然光侧逆光勾边，浅景深焦点跟随，机身轻微晃动，Canon Log 3，4K 60fps",
        "无人机航拍，赛博朋克城市，正午顶光俯仰运镜，GPS悬停电子增稳，徕卡色彩风格，H.265 10bit录制",
        "斯坦尼康拍摄，萤火虫森林，360度匀速环绕，长镜头一镜到底，动态平衡调平，S-Log3灰度模式",
    ]

    for i, raw in enumerate(samples, 1):
        enhanced, neg = enhance_prompt(raw)
        print(f"\n{'='*70}")
        print(f"原始 [{i}]:")
        print(f"  {raw}")
        print(f"\n清洗后（参数标签全删）:")
        print(f"  {clean_prompt(raw)}")
        print(f"\n增强后（V2 写实强化）:")
        print(f"  {enhanced}")
        print(f"\nnegative_prompt（V2 涂抹感强化）:")
        print(f"  {neg}")
