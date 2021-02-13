# -*- coding: utf-8 -*-

# Run this app with `python dsmt_app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import os
import json
import datetime

import docker
import dash
import dash_html_components as html
import dash_core_components as dcc
from dash.dependencies import Input, Output, State
import plotly
import psutil

from dsmt.process import ps_query
from dsmt.speed import test_speed


app = dash.Dash(__name__)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.json")
with open(CONFIG_FILE, "r") as f:
    CONFIG = json.load(f)


check_img = html.Img(src="/assets/check.png", style={"width": "30px", "height": "30px"})
x_img = html.Img(src="/assets/x.png", style={"width": "30px", "height": "30px"})
update_interval = CONFIG["dsmt"]["update_interval"]
speed_interval = int(CONFIG["dsmt"]["inet_interval"])
port = int(CONFIG["dsmt"]["port"])
interval = 0.1

table_header_style = "has-text-white"
table_style = "table is-bordered is-centered has-text-white has-background-dark"
header_style = "title is-2 has-text-white"
box_style = "box is-fullwidth has-background-dark"
monospace_style = "is-family-monospace"

divider = html.Div(className="is-divider")

def html_status_tables():



    # Process scanning
    ps_config = CONFIG["ps"]

    # Add this process into the
    ptable_header = [html.Tr([html.Th(label, className=table_header_style) for label in ["Process Group", "Running?", "PIDs", "Description", "Ports", "CPU"]])]
    ptable_rows = []

    for pname, pinfo in ps_config.items():

        pq = pinfo["query"]
        plist = ps_query(pq)

        if plist:
            running = True
            pids_formatted =  ",".join(str(p.pid) for p in plist)
            plist_cpu = sum([p.cpu_percent(interval=interval) for p in plist])/psutil.cpu_count()
            plist_cpu = f"{plist_cpu}%"
        else:
            if pname == "dsmt_app":
                running = True
                pids_formatted = os.getpid()
                plist_cpu = psutil.Process(pids_formatted).cpu_percent(interval=interval)/psutil.cpu_count()
                plist_cpu = f"{plist_cpu}%"
            else:
                running = False
                pids_formatted = "null"
                plist_cpu = "null"

        ptable_rows.append(html.Tr([
            html.Td(pname, className=monospace_style),
            html.Td(check_img if running else x_img),
            html.Td(pids_formatted),
            html.Td(pinfo['description']),
            html.Td(pinfo["ports"]),
            html.Td(plist_cpu)
        ]))


    proc_table = html.Table(ptable_header + ptable_rows, className=table_style)
    proc_div = html.Div([html.Div("Processes", className=header_style),  proc_table], className=box_style)

    # Docker with default configuration running locally
    if CONFIG["docker"]:
        dtable_header = [html.Tr([html.Th(label, className=table_header_style) for label in ["Container Name", "Running?", "Status", "Image", "Ports"]])]
        dtable_rows = []

        client = docker.from_env()
        for c in client.containers.list(all=True):

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
                html.Td(c.name, className=monospace_style),
                html.Td(check_img if running else x_img),
                html.Td(c.status),
                html.Td(c.image.attrs["RepoTags"][0]),
                html.Td(ports_html),
            ]))

        docker_table = html.Table(dtable_header + dtable_rows, className=table_style)
        docker_div = html.Div([html.Div("Docker containers", className=header_style), docker_table], className=box_style)
    else:
        docker_div = html.Div(children='')

    # SystemD services
    stable_header = [html.Tr([html.Th(label, className=table_header_style) for label in ["Service name",  "Running?", "Main PID", "Description", "Ports", "CPU"]])]
    stable_rows = []
    for sname, sinfo in CONFIG["systemd"].items():
        squery = sinfo["query"]
        info = os.popen(f'systemctl status {squery}').read()
        infolist = [i.strip() for i in info.split("\n")]

        desc_dirty = infolist[0]
        status_dirty = [i for i in infolist if "Active: " in i][0]
        running = True if "(running) since" in status_dirty else False

        if running:
            pid_dirty = [i for i in infolist if "Main PID:" in i][0].replace("Main PID: ", "")
            pid_clean = int(pid_dirty.split(" ")[0].strip())
        else:
            pid_dirty = "null"
            pid_clean = "null"

        try:
            cpu_usage = psutil.Process(pid_clean).cpu_percent(interval=interval)
            cpu_usage = f"{cpu_usage}%"
        except:
            cpu_usage = "N/A"

        stable_rows.append(html.Tr([
            html.Td(sname, className=monospace_style),
            html.Td(check_img if running else x_img),
            html.Td(pid_dirty),
            html.Td(f"{sinfo['description']} ({desc_dirty})"),
            html.Td(", ".join([str(port) for port in sinfo["ports"]])),
            html.Td(cpu_usage)
        ]))

    systemd_table = html.Table(stable_header + stable_rows,  className=table_style)
    systemd_div = html.Div([html.Div("SystemD services", className=header_style), systemd_table], className=box_style)
    return html.Div(id="display", children=[proc_div, divider, docker_div, divider, systemd_div])


# todo: remove this
import random

def html_uptime_graphs(prev_data):


    # debugging
    # prev_data["pings"].append(random.random())
    # prev_data["downs"].append(random.random() * 1000)
    # prev_data["ups"].append(random.random() * 10)

    print("about to run speedtest")

    results = test_speed()
    prev_data["pings"].append(results["ping"])
    prev_data["downs"].append(results["download"]/1e6)
    prev_data["ups"].append(results["upload"]/1e6)


    prev_data["datetimes"].append(results["timestamp"])

    fig = plotly.tools.make_subplots(rows=3, cols=1, subplot_titles=("Ping", "Download", "Upload"))

    fig.append_trace({
        "y": prev_data["pings"],
        "x": prev_data["datetimes"],
        "name": "pings",
        "mode": "lines+markers",
        "type": "scatter"
    }, 1, 1)

    fig.append_trace({
        "y": prev_data["downs"],
        "x": prev_data["datetimes"],
        "name": "downloads",
        "mode": "lines+markers",
        "type": "scatter"
    }, 2, 1)

    fig.append_trace({
        "y": prev_data["ups"],
        "x": prev_data["datetimes"],
        "name": "uploads",
        "mode": "lines+markers",
        "type": "scatter",
    }, 3, 1)

    fig.update_layout(
        autosize=False,
        # width=1200,
        height=1000,
        margin=dict(
            l=50,
            r=50,
            b=100,
            t=100,
            pad=4
        ),
        template="plotly_dark"
    )
    return fig




@app.callback(
    Output('holder-service', 'children'),
    Input('interval-service', 'n_intervals')
)
def update_output_div(input_value):
    return html_status_tables()



@app.callback(
    Output('speed-update-graph', 'figure'),
    Input('interval-speed', 'n_intervals'),
    State('speed-update-graph', 'figure')
)
def update_uptime_graphs(interval, figure):

    if figure:
        ping_data = figure["data"][0]
        datetimes = ping_data["x"]
        pings = ping_data["y"]


        down_data = figure["data"][1]
        download = down_data["y"]

        up_data = figure["data"][2]
        upload = up_data["y"]

        prev_data = {"pings": pings, "downs": download, "ups": upload, "datetimes": datetimes}
    else:
        prev_data = {"pings": [], "downs": [], "ups": [], "datetimes": []}
    return html_uptime_graphs(prev_data)



@app.callback(
    Output("speed-info", "children"),
    Input("interval-speed", "n_intervals")
)
def update_uptime_title(interval):
    results = test_speed(ping_only=True)

    host_url = results["server"]["url"]
    host_name = results["server"]["name"]
    ip = results["client"]["ip"]
    isp = results["client"]["isp"]

    html_url = html.Div(f"{host_url}", className=monospace_style + " has-text-white is-5")
    html_info = html.Div(f"{host_name} from {ip} (ISP {isp})", className="has-text-white is-3")
    return html.Div(children=[
        html_url,
        html_info
    ],
    className="has-margin-20")


app.layout = html.Div(children=[
    html.Div(id="holder-service"),
    dcc.Interval(
            id='interval-service',
            interval=update_interval, # in milliseconds
            n_intervals=0
        ),

    html.Div(
        children=[
            html.Div(children="ISP Monitoring", className=header_style),
            html.Div(id="speed-info"),
            dcc.Graph(id="speed-update-graph", className="is-centered")
            ],
        className=box_style
     ),
    dcc.Interval(
        id='interval-speed',
        interval=speed_interval,  # in milliseconds
        n_intervals=0
    ),
],
className="container is-centered has-background-dark"
)

app.title = "dmst"


if __name__ == '__main__':
    app.run_server(debug=True, port=port)
    # app.run_server(host="0.0.0.0", port=port)