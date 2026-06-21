#!/usr/bin/env python3
"""
测试脚本：验证 token 权限检查

使用方式：
  python3 test_token_permissions.py [base_url] [token]
  
示例：
  python3 test_token_permissions.py https://api.ccbot.chat sk-989ef22b99701ed87644e6631dcf1b621651325a544a0fd1
"""

import sys
import httpx
import json
from datetime import datetime

def print_section(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def test_token_permissions(base_url: str, token: str):
    """测试 token 的权限检查"""
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"\n测试时间: {datetime.now().isoformat()}")
    print(f"Base URL: {base_url}")
    print(f"Token: {token[:20]}...{token[-10:]}")
    
    # 测试 1: 无 model 参数
    print_section("测试 1: 无 model 参数（应显示允许的模型）")
    payload = {
        "messages": [{"role": "user", "content": "test"}],
        "stream": False
    }
    
    try:
        response = httpx.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"状态码: {response.status_code}")
        data = response.json()
        if "detail" in data:
            print(f"错误信息: {data['detail']}")
        if "error" in data:
            print(f"Error: {data['error']}")
        print(f"是否包含'Allowed models'或'restricted to': {'是' if 'Allowed models' in str(data) or 'restricted to' in str(data) else '否'}")
    except Exception as e:
        print(f"❌ 连接错误: {e}")
    
    # 测试 2: model=auto
    print_section("测试 2: model='auto'（应自动选择可用模型）")
    payload["model"] = "auto"
    
    try:
        response = httpx.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 成功")
            print(f"使用的模型: {data.get('model', 'N/A')}")
        else:
            data = response.json()
            if "detail" in data:
                print(f"❌ 错误: {data['detail']}")
    except Exception as e:
        print(f"❌ 连接错误: {e}")
    
    # 测试 3: model=glm-5.2（假设这是允许的）
    print_section("测试 3: model='glm-5.2'（假设这是允许的模型）")
    payload["model"] = "glm-5.2"
    
    try:
        response = httpx.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 成功")
            print(f"使用的模型: {data.get('model', 'N/A')}")
            msg = data['choices'][0]['message']['content']
            print(f"回复内容（前50字符）: {msg[:50]}...")
        else:
            data = response.json()
            if "detail" in data:
                print(f"❌ 错误: {data['detail']}")
    except Exception as e:
        print(f"❌ 连接错误: {e}")
    
    # 测试 4: model=deepseek-v4-pro（应被拒）
    print_section("测试 4: model='deepseek-v4-pro'（应被拒，显示允许的模型）")
    payload["model"] = "deepseek-v4-pro"
    
    try:
        response = httpx.post(
            f"{base_url}/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=10
        )
        print(f"状态码: {response.status_code}")
        data = response.json()
        if response.status_code == 403:
            print(f"✅ 正确拒绝 (403)")
        else:
            print(f"⚠️ 意外状态码: {response.status_code}")
        
        if "detail" in data:
            print(f"错误信息: {data['detail']}")
            # 检查是否显示了允许的模型
            if "Allowed models" in data['detail']:
                print("✅ 错误消息包含允许的模型列表")
            else:
                print("⚠️ 错误消息未显示允许的模型列表")
    except Exception as e:
        print(f"❌ 连接错误: {e}")
    
    # 总结
    print_section("测试总结")
    print("""
预期结果:
  ✅ 测试 1: 400 错误 + 提示模型限制信息
  ✅ 测试 2: 200 成功 + 使用允许的模型
  ✅ 测试 3: 200 成功 + 使用 glm-5.2
  ✅ 测试 4: 403 拒绝 + 显示允许的模型列表

如果所有测试都通过，说明权限检查工作正常。
    """)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    
    base_url = sys.argv[1]
    token = sys.argv[2]
    
    test_token_permissions(base_url, token)
