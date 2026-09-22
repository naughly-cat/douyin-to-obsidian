# 参与贡献

感谢你愿意改进 douyin-to-obsidian。

## 开发环境

```bash
git clone https://github.com/naughly-cat/douyin-to-obsidian.git
cd douyin-to-obsidian
python3 -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

## 提交前检查

```bash
python -m pytest -q
douyin-to-obsidian --help
python -m pip wheel --no-deps .
```

修复 bug 时请先增加能复现问题的测试。测试必须离线运行，不得依赖真实社媒账号、登录态或仍可访问的第三方作品。

## Pull Request

1. 每个 PR 聚焦一个清晰问题；
2. 说明行为变化、验证方式和兼容性影响；
3. 不提交模型、媒体、Obsidian 私人库、Cookie、访问令牌或转写缓存；
4. 示例使用虚构人物、虚构指标和 `example.com` 链接；
5. 涉及平台解析变化时，提供脱敏后的最小 HTML/JSON fixture，不提交完整受版权保护内容。

安全漏洞请按 [SECURITY.md](SECURITY.md) 私下报告，不要提交公开 Issue。
