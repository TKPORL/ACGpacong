import json

with open('data/acgyx_latest.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

items = d['items']

print(f'总条目: {len(items)}')

empty_titles = [it for it in items if not it.get('title') or it.get('title').strip() == '']
print(f'\n空标题数量: {len(empty_titles)}')
for i, it in enumerate(empty_titles[:10]):
    print(f'  [{i+1}] raw_title: {repr(it.get("raw_title", "")[:80])}')
    print(f'       category: {it.get("category")}')
    print(f'       url: {it.get("url", "")[:50]}')

dual_links = [it for it in items if (it.get('yun_links') and it.get('baidu_links'))]
print(f'\n双链接(同时有移动云和百度云): {len(dual_links)}')
for i, it in enumerate(dual_links[:5]):
    print(f'  [{i+1}] {it.get("category")} - {it.get("title", "")[:50]}')
    print(f'       yun_links: {len(it.get("yun_links", []))}')
    print(f'       baidu_links: {len(it.get("baidu_links", []))}')
