import psutil


def ps_query(query):
    running = []
    for p in psutil.process_iter():
        if query in " ".join(p.cmdline()):
            running.append(p)
    return running
