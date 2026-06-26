import os
import base64
import json
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()


def save_image_from_response(data: dict, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image_data = None

    # 情况一：data[0] 返回图片
    if isinstance(data.get("data"), list) and data["data"]:
        item = data["data"][0]
        if isinstance(item, dict):
            image_data = (
                item.get("b64_json")
                or item.get("base64")
                or item.get("image_base64")
                or item.get("url")
            )

    # 情况二：choices[0].message.content 返回图片
    if image_data is None and isinstance(data.get("choices"), list) and data["choices"]:
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content")

        if isinstance(content, str):
            image_data = content

        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    image_data = (
                        part.get("b64_json")
                        or part.get("base64")
                        or part.get("image_base64")
                        or part.get("url")
                    )

                    if not image_data and isinstance(part.get("image_url"), dict):
                        image_data = part["image_url"].get("url")

                    if image_data:
                        break

    if not image_data:
        print("\n无法识别图片返回格式。完整响应如下：\n")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        raise ValueError("Image response format not recognized.")

 
    # 返回 Markdown 图片格式：![image](https://xxx.png)
    if isinstance(image_data, str) and image_data.strip().startswith("!["):
        print("检测到 Markdown 图片格式，正在提取图片 URL...")

        start = image_data.find("(")
        end = image_data.find(")", start + 1)

        if start != -1 and end != -1:
            image_url = image_data[start + 1:end].strip()
            print("提取到图片 URL：", image_url)

            img_resp = requests.get(image_url, timeout=180)
            img_resp.raise_for_status()
            output_path.write_bytes(img_resp.content)
            return

    # 返回纯 URL
    if isinstance(image_data, str) and image_data.startswith("http"):
        print("检测到图片 URL，正在下载图片...")
        img_resp = requests.get(image_data, timeout=180)
        img_resp.raise_for_status()
        output_path.write_bytes(img_resp.content)
        return

    # 返回 data:image/png;base64,...
    if isinstance(image_data, str) and image_data.startswith("data:image"):
        print("检测到 data:image base64，正在保存图片...")
        image_data = image_data.split(",", 1)[1]

    # 返回纯 base64
    try:
        print("检测到 base64，正在保存图片...")
        img_bytes = base64.b64decode(image_data)
        output_path.write_bytes(img_bytes)
    except Exception as e:
        print("\n图片数据不是 URL，也不是可解析的 base64。")
        print("原始内容前 500 字符如下：\n")
        print(str(image_data)[:500])
        raise e


def main():
    base_url = os.getenv("IMAGE_API_BASE_URL", "").rstrip("/")
    api_key = os.getenv("IMAGE_API_KEY", "")
    model = os.getenv("IMAGE_MODEL", "agnes-image-2.1-flash")
    timeout = int(os.getenv("IMAGE_API_TIMEOUT", "300"))
    size = os.getenv("IMAGE_SIZE", "1024x768")

    if not base_url:
        raise RuntimeError("缺少 IMAGE_API_BASE_URL，请检查 .env 文件。")

    if not api_key:
        raise RuntimeError("缺少 IMAGE_API_KEY，请检查 .env 文件。")

    # Agnes 图片生成接口
    url = f"{base_url}/images/generations"

    prompt = """
生成一张漫画插图。

主题：有目标才有动力。

画面要求：
- 干净白底
- 扁平化漫画风
- 两个人物，内容自己构思
- 不要复杂背景
- 不要密集文字
- 图片质量高

Generate exactly one image asset. Return only the image result.
"""

    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    print("=" * 60)
    print("开始测试 Agnes 图片 API")
    print("=" * 60)
    print("请求地址：", url)
    print("模型：", model)
    print("尺寸：", size)
    print("输出文件：outputs/images/test_contract.png")
    print("=" * 60)

    resp = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=timeout,
    )

    print("HTTP 状态码：", resp.status_code)

    if resp.status_code != 200:
        print("\n请求失败，响应内容如下：\n")
        print(resp.text)
        resp.raise_for_status()

    data = resp.json()

    output_path = Path("outputs/images/test_contract.png")
    save_image_from_response(data, output_path)

    print("\n图片生成成功！")
    print("保存位置：", output_path.resolve())
    print("=" * 60)


if __name__ == "__main__":
    main()