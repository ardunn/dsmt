import platform  # For getting the operating system name
import subprocess  # For executing a shell command
import speedtest


def test_speed(ping_only=False):

    try:
        s = speedtest.Speedtest()
        s.get_servers()
        s.get_best_server()

        if not ping_only:
            s.download()
            s.upload()
        res = s.results.dict()
    except speedtest.ConfigRetrievalError:
        res = None
    return res


if __name__ == "__main__":
    print(test_speed())