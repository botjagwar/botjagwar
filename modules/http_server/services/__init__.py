# coding: utf8
import time


def example(**params):
    """
    Example function to use for server POC.
    Args:
        **params: keyword arguments representing GET params      
    Returns:
        str() object

    """
    ct_time = tuple(time.localtime())
    ret = u"みんなさんこんにちは、今日は%d年%d月%d日%d時%d分" % ct_time[:5]
    ret += u"<br><br><br><br>設定は、"
    for k, v in params.items():
        ret += k + u"(" + v + u")"

    return ret.encode('utf8')
