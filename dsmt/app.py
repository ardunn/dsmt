# -*- coding: utf-8 -*-

# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import os
import json
import docker
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output
import psutil

from dsmt.process import ps_query


app = dash.Dash(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.json")
with open(CONFIG_FILE, "r") as f:
    CONFIG = json.load(f)


check_img = html.Img(src="/assets/check.png", style={"width": "30px", "height": "30px"})
x_img = html.Img(src="/assets/x.png", style={"width": "30px", "height": "30px"})
interval = 0.1


def html_status_tables():

    # Process scanning
    PS_CONFIG = CONFIG["ps"]
    ptable_header = [html.Tr([html.Th(label) for label in ["Process Group", "Running?", "PIDs", "Description", "Ports", "CPU"]])]
    ptable_rows = []

    for pname, pinfo in PS_CONFIG.items():

        pq = pinfo["query"]
        plist = ps_query(pq)
        if plist:
            running = True
            pids_formatted =  ",".join(str(p.pid) for p in plist)
            plist_cpu = sum([p.cpu_percent(interval=interval) for p in plist])/psutil.cpu_count()
            plist_cpu = f"{plist_cpu}%"
        else:
            running = False
            pids_formatted = "null"
            plist_cpu = "null"

        ptable_rows.append(html.Tr([
            html.Td(pname),
            html.Td(check_img if running else x_img),
            html.Td(pids_formatted),
            html.Td(pinfo['description']),
            html.Td(pinfo["ports"]),
            html.Td(plist_cpu)
        ]))

    proc_table = html.Table(ptable_header + ptable_rows)
    proc_div = html.Div([html.H2("Processes"),  proc_table])

    # Docker with default configuration running locally
    if CONFIG["docker"]:
        dtable_header = [html.Tr([html.Th(label) for label in ["Container Name", "Running?", "Status", "Image", "Ports"]])]
        dtable_rows = []

        client = docker.from_env()
        for c in client.containers.list():

            running = True if c.status == "running" else False
            if c.ports:
                ports = []
                for cport, hportset in c.ports.items():
                    hport = hportset[0]["HostPort"] if hportset else "null"
                    ports.append(f"{cport} (container) -> {hport}")
                ports_html = html.Div([html.Div(port) for port in ports])
            else:
                ports_html = "null"

            dtable_rows.append(html.Tr([
                html.Td(c.name),
                html.Td(check_img if running else x_img),
                html.Td(c.status),
                html.Td(c.image.attrs["RepoTags"][0]),
                html.Td(ports_html)
            ]))

        docker_table = html.Table(dtable_header + dtable_rows)
        docker_div = html.Div([html.H2("Docker containers"), docker_table])
    else:
        docker_div = html.Div(children='')

    # SystemD services
    stable_header = [html.Tr([html.Th(label) for label in ["Service name",  "Running?", "Main PID", "Description", "Ports", "CPU"]])]
    stable_rows = []
    for sname, sinfo in CONFIG["systemd"].items():
        squery = sinfo["query"]
        info = os.popen(f'systemctl status {squery}').read()
        infolist = [i.strip() for i in info.split("\n")]

        desc_dirty = infolist[0]
        pid_dirty = [i for i in infolist if "Main PID:" in i][0].replace("Main PID: ", "")
        pid_clean = int(pid_dirty.split(" ")[0].strip())
        status_dirty = [i for i in infolist if "Active: " in i][0]
        running = True if "(running) since" in status_dirty else False



        try:
            cpu_usage = psutil.Process(pid_clean).cpu_percent(interval=interval)
            cpu_usage = f"{cpu_usage}%"
        except:
            cpu_usage = "N/A"

        stable_rows.append(html.Tr([
            html.Td(sname),
            html.Td(check_img if running else x_img),
            html.Td(pid_dirty),
            html.Td(f"{sinfo['description']} ({desc_dirty})"),
            html.Td(", ".join([str(port) for port in sinfo["ports"]])),
            html.Td(cpu_usage)
        ]))

    systemd_table = html.Table(stable_header + stable_rows)
    systemd_div = html.Div([html.H2("SystemD services"), systemd_table])
    return html.Div(id="display", children=[proc_div, docker_div, systemd_div])



@app.callback(
    Output('display-holder', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_output_div(input_value):
    return html_status_tables()

app.layout = html.Div(children=[
    html.Div(id="display-holder"),
    dcc.Interval(
            id='interval-component',
            interval=1000, # in milliseconds
            n_intervals=0
        )
])

if __name__ == '__main__':
    app.run_server(debug=True)