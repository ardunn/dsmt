import psutil


def ps_query(query):
    running = []
    for p in psutil.process_iter():
        if query in p.name():
            running.append(p)
    return running