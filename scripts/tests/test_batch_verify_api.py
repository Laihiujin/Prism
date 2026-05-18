"""
测试账号批量验证API接口
模拟前端调用批量验证接口
"""
import asyncio
import httpx
import time


async def test_batch_verify_api():
    """测试批量验证API"""
    print("=" * 60)
    print("测试账号批量验证API")
    print("=" * 60)

    url = "http://localhost:8000/api/v1/accounts/batch-verify"

    print(f"\n请求URL: {url}")
    print("请求方法: POST")

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            print("\n发送批量验证请求...")
            start = time.time()

            response = await client.post(url)
            elapsed = time.time() - start

            print(f"\n响应状态码: {response.status_code}")
            print(f"总耗时: {elapsed:.2f}秒")

            if response.status_code == 200:
                data = response.json()
                print("\n响应数据:")
                print(f"  success: {data.get('success')}")
                print(f"  message: {data.get('message')}")

                result_data = data.get('data', {})
                print(f"\n验证统计:")
                print(f"  总账号数: {result_data.get('total')}")
                print(f"  有效账号: {result_data.get('valid')}")
                print(f"  失效账号: {result_data.get('expired')}")
                print(f"  网络错误: {result_data.get('network_error')}")
                print(f"  其他错误: {result_data.get('error')}")

                # 显示前5个账号的详情
                details = result_data.get('details', [])
                if details:
                    print(f"\n前5个账号详情:")
                    for i, detail in enumerate(details[:5]):
                        account_id = detail.get('account_id', 'N/A')
                        platform = detail.get('platform', 'N/A')
                        status = detail.get('status', 'N/A')
                        name = detail.get('name') or 'N/A'
                        print(f"  {i+1}. {account_id[:20]}... - {platform} - {status} - {name}")

                # 计算性能指标
                total = result_data.get('total', 0)
                if total > 0:
                    avg_time = elapsed / total * 1000
                    print(f"\n性能指标:")
                    print(f"  平均验证时间: {avg_time:.0f}ms/账号")
                    print(f"  总吞吐量: {total/elapsed:.1f}账号/秒")

            else:
                print(f"\n请求失败: {response.text}")

    except httpx.ConnectError:
        print("\n错误: 无法连接到后端服务器")
        print("请确保后端服务正在运行: python syn_backend/fastapi_app/main.py")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)


async def test_single_verify_api():
    """测试单个账号验证API"""
    print("\n" + "=" * 60)
    print("测试单个账号验证API")
    print("=" * 60)

    # 首先获取账号列表
    list_url = "http://localhost:8000/api/v1/accounts"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 获取账号列表
            print("\n获取账号列表...")
            response = await client.get(list_url)

            if response.status_code != 200:
                print(f"获取账号列表失败: {response.status_code}")
                return

            data = response.json()
            accounts = data.get('data', {}).get('items', [])

            if not accounts:
                print("没有找到账号")
                return

            # 测试第一个账号
            test_account = accounts[0]
            account_id = test_account['account_id']

            print(f"\n测试账号: {account_id}")
            print(f"平台: {test_account['platform']}")

            verify_url = f"http://localhost:8000/api/v1/accounts/{account_id}/verify"
            print(f"\n请求URL: {verify_url}")

            start = time.time()
            response = await client.post(verify_url)
            elapsed = time.time() - start

            print(f"\n响应状态码: {response.status_code}")
            print(f"耗时: {elapsed*1000:.0f}ms")

            if response.status_code == 200:
                result = response.json()
                print(f"\n验证结果:")
                print(f"  status: {result.get('status')}")
                print(f"  user_id: {result.get('user_id')}")
                print(f"  name: {result.get('name')}")
                print(f"  avatar: {result.get('avatar')}")
                if result.get('error'):
                    print(f"  error: {result['error']}")
            else:
                print(f"\n请求失败: {response.text}")

    except httpx.ConnectError:
        print("\n错误: 无法连接到后端服务器")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)


async def main():
    """运行所有API测试"""
    # 测试批量验证
    await test_batch_verify_api()

    # 测试单个验证
    await test_single_verify_api()


if __name__ == "__main__":
    asyncio.run(main())
