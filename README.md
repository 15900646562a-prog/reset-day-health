# SEO Factory — Reset Day

把"现有物资"(fendan 文案 + 口播脚本)批量变成 SEO 文章页,发 GitHub Pages。
**隔离工具**:自成一仓,不碰任何主线代码/分支/资源。

## 流水线
```
src/seo_build.py   收集物资(creative_factory output/copyclone + 配音待审.md)
                   → LLM 逐篇写 SEO 文章(带合规闸) → content/articles/*.json
src/render.py      文章 JSON → docs/*.html + index + sitemap.xml + robots.txt(纯代码)
```

## 用法
```bash
# 1) 配 key(yunwu 代理;不进 git):
echo 'OPENAI_API_KEY=sk-...'             >  .env
echo 'OPENAI_API_BASE=https://yunwu.ai/v1' >> .env
# 2) 跑:
python3 src/seo_build.py     # 写文章(可重跑,已生成的跳过)
python3 src/render.py        # 渲染成站
# 3) 发布:推到 GitHub,Pages 从 main /docs 服务
git add -A && git commit -m "..." && git push
```

## 产品口径(war-room 决策 R8)
T-Patch = **全球首款外用(透皮、无针)替尔泊肽**。文章公开命名 tirzepatide、定位无针外用、导向社区/下单。
合规后置闸只 flag 纯编造项(假 FDA 认证/保证/编造数字/自称执业医生),供人审。

## 5 个内容簇
life-after-the-shot · affordable-alternatives · midlife-metabolism · pcos-insulin · food-noise
