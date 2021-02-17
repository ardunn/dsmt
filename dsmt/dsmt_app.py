# -*- coding: utf-8 -*-

# Run this app with `python dsmt_app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

import os
import json
import datetime

import pandas as pd
import docker
import dash
import dash_html_components as html
import dash_core_components as dcc
import dash_daq as daq
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
days_range = int(CONFIG["dsmt"]["inet_days_range"])
port = int(CONFIG["dsmt"]["port"])
interval = 0.1
isp_path = os.path.join(os.path.dirname(CONFIG_FILE), "isp.csv")
server_name = CONFIG["dsmt"]["server_name"]
server_description = CONFIG["dsmt"]["server_description"]
server_file = os.path.join(os.path.dirname(CONFIG_FILE), "server_state.json")
default_server_state = \
    {
        "isp_monitoring": False,
    }

page_header_style = "title has-text-white is-1"
page_description_style = "has-text-white is-4"
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


def run_speedtest_update(prev_data):

    print("running full speedtest")
    results = test_speed()
    print("done running full speedtest")

    if results:
        prev_data["pings"].append(results["ping"])
        prev_data["downs"].append(results["download"]/1e6)
        prev_data["ups"].append(results["upload"]/1e6)
        prev_data["datetimes"].append(datetime.datetime.now().isoformat())
    else:
        prev_data["pings"].append(10000)
        prev_data["downs"].append(0)
        prev_data["ups"].append(0)
        prev_data["datetimes"].append(datetime.datetime.now().isoformat())

    # save the file in some persistent filename
    pd.DataFrame(prev_data).to_csv(isp_path, index=False)
    return make_uptime_figures(prev_data)



def make_uptime_figures(prev_data):
    ping_recent = int(prev_data["pings"][-1])
    ping_recent = f"{ping_recent} ms" if ping_recent < 10000 else "No connection"
    ping_title = f"Ping (current = {ping_recent})"

    down_recent = prev_data["downs"][-1]
    down_title = f"Download (current = {int(down_recent)} MBits/s)"

    up_recent = prev_data["ups"][-1]
    up_title = f"Upload (current = {int(up_recent)} MBits/s)"

    fig = plotly.tools.make_subplots(rows=3, cols=1, subplot_titles=(ping_title, down_title, up_title))

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


    now = datetime.datetime.now()
    daterange = [now - datetime.timedelta(days=days_range), now]

    fig.update_yaxes(title_text="ping (ms) [log scale]", type="log", row=1, col=1)
    fig.update_yaxes(title_text="MBit/s", row=2, col=1)
    fig.update_yaxes(title_text="MBit/s", row=3, col=1)
    fig.update_xaxes(showticklabels=False, row=1, col=1, range=daterange)
    fig.update_xaxes(showticklabels=False, row=2, col=1, range=daterange)
    fig.update_xaxes(range=daterange)
    fig.update_layout(
        autosize=True,
        # width=2000,
        height=1000,
        margin=dict(
            l=50,
            r=50,
            b=100,
            t=100,
            pad=4
        ),
        template="plotly_dark",
        showlegend=False
    )
    return fig


def get_historical_data():
    if os.path.exists(isp_path):
        df = pd.read_csv("isp.csv", index_col=False)
        prev_data = {c: df[c].tolist() for c in ["pings", "downs", "ups", "datetimes"]}
    else:
        prev_data = {"pings": [], "downs": [], "ups": [], "datetimes": []}
    return prev_data



def server_state(write=None):
    # Write the state
    if write is not None:
        with open(server_file, "w") as f:
            json.dump(write, f)
            return None

    # Obtain the state, if it exists
    else:
        if not os.path.exists(server_file):
            with open(server_file, "w") as f:
                json.dump(default_server_state, f)
            return default_server_state
        else:
            with open(server_file, "r") as f:
                state = json.load(f)
            return state



@app.callback(
    Output('holder-service', 'children'),
    Input('interval-service', 'n_intervals')
)
def update_output_div(input_value):
    return html_status_tables()



@app.callback(
    Output('speed-update-graph', 'figure'),
    Input('interval-speed', 'n_intervals'),
    State("tog-switch", "value"),
    State('speed-update-graph', 'figure')
)
def update_uptime_graphs(interval, tog_value, figure):

        if figure and tog_value:
            ping_data = figure["data"][0]
            datetimes = ping_data["x"]
            pings = ping_data["y"]

            down_data = figure["data"][1]
            download = down_data["y"]

            up_data = figure["data"][2]
            upload = up_data["y"]

            prev_data = {"pings": pings, "downs": download, "ups": upload, "datetimes": datetimes}
            return run_speedtest_update(prev_data)

        else:
            return make_uptime_figures(get_historical_data())


@app.callback(
    Output("interval-speed", "disabled"),
    Input("tog-switch", "value")
)
def toggle_monitoring(tog_value):
    return tog_value != True


@app.callback(
    Output("speed-info", "children"),
    Input("interval-speed", "n_intervals"),
    State("tog-switch", "value")
)
def update_uptime_title(interval, tog_switch_state):
    if tog_switch_state:
        print("running ping only speedtest")
        results = test_speed(ping_only=True)
        print("ping only speedtest run!")
        if results:
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
        else:
            return html.Div("No connection.", className="has-margin-20 has-text-white is-5")
    else:
        return html.Div(children="")

@app.callback(
    Output("isp-testing-holder", "style"),
    Input("tog-switch", "value"),
)
def toggle_isp_testing(toggle_value):
    if toggle_value:
        # update the server state
        server_state(write={"isp_monitoring": True})
        return {'display': 'block'}
    else:
        server_state(write={"isp_monitoring": False})
        return {'display': 'none'}


# If another user on the webpage toggles it off, make sure the page the first user is on reflects the monitoring state change
@app.callback(
    Output("tog-switch", "value"),
    Input("sync_server_state", "n_intervals"),
)
def sync_server_state_from_fs(interval):
    state = server_state()

    isp_monitoring_state = state["isp_monitoring"]
    return isp_monitoring_state


prev_data = get_historical_data()
tmp_figure = make_uptime_figures(prev_data)

app.layout = html.Div(children=[
    html.Div([html.Div(server_name, className=page_header_style), html.Div(server_description, className=page_description_style)], className="has-margin-20"),
    html.Div(id="holder-service"),
    dcc.Interval(
            id='interval-service',
            interval=update_interval, # in milliseconds
            n_intervals=0
        ),

    html.Div(
        children=[
            html.Div(children="ISP Monitoring", className=header_style),
            daq.ToggleSwitch(id="tog-switch", size=75, label='Toggle ISP Monitoring', labelPosition='bottom', theme="dark", className=page_description_style, value=server_state()["isp_monitoring"]),
            html.Div(id="isp-testing-holder", children=html.Div(
                id="graphs-holder",
                children=[
                    html.Div(id="speed-info"),
                    dcc.Graph(id="speed-update-graph", className="is-centered", figure=tmp_figure),
            dcc.Interval(
                    id='interval-speed',
                    interval=speed_interval,  # in milliseconds
                    n_intervals=0
                )
                    ])),
            dcc.Interval(id="sync_server_state", interval=1000)
        ],
        className=box_style + " has-margin-top-30"
     ),
],
className="container is-centered has-background-dark"
)

app.title = "dmst"


if __name__ == '__main__':
    # app.run_server(debug=True, host="0.0.0.0", port=port)
    app.run_server(host="0.0.0.0", port=port)