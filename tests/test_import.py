# input: mindclaw 包
# output: 冒烟测试
# pos: 基础导入验证
# UPDATE: 一旦本文件被更新，务必更新开头注释及所属文件夹的 _ARCHITECTURE.md


def test_import():
    import mindclaw

    assert mindclaw.__version__ == "0.1.0"
