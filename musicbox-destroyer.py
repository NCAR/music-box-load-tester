# ipmort packages for networking
import socket
import sys
import time
import os
import subprocess
import signal
import threading
import random
import string
import re
import json
import urllib
import urllib.request
import urllib.parse
import requests
import base64
import ssl
import functools
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console # for pretty printing
from rich.table import Table
from rich.live import Live
# give us the ability to ignore ssl errors
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context
# create base table for progress updates for each session using rich
table = Table(show_header=True, header_style="bold magenta")
console = Console()
live = Live(table, auto_refresh=False)
# futures = []
start_time = time.time()
# thread pool
pool = ThreadPoolExecutor(max_workers=1)
TABLE_DATA = []
# make sure table doesn't update too fast by keeping track of last update
currently_updating = False
# class for each session of the musicbox
class MusicBoxSession:
    # store uid 
    uid = ""
    # session number
    session = 0
    done = False
    should_stop = False
    # constructor
    def __init__(self, uid, session):
        self.uid = uid
        self.session = session
    
    # return the uid
    def getUid(self):
        return self.uid
    
    # return the session number
    def getSession(self):
        return self.session
    # api call helper function
    def apiCall(self, base_url, data, post=False):
        # keep track of how long it takes and whether it was successful
        start_time = time.time()
        success = True
        response = None
        # try to make the api call
        try:
            # make custom request with uid in cookie sessionid
            # and referer
            
            # only add data if it is not empty
            if data != "" and type(data) == str:
                data = data.encode("utf-8")
            # set up required request headers
            headers = {
                "Referer": "https://musicbox.acom.ucar.edu/",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:60.0) Gecko/20100101 Firefox/60.0",
                "Accept": "application/json"
            }
            if self.uid != "":
                headers["Cookie"] = "sessionid=" + self.uid
            # make request
            if post:
                response = requests.post(base_url, data=data, headers=headers)
            else:
                # check if we have data to send
                if data != "":
                    # check if data is a json object
                    if type(data) == str:
                        response = requests.get(base_url, data=data, headers=headers)
                    else:
                        response = requests.get(base_url, json=data, headers=headers)
                else:
                    response = requests.get(base_url, headers=headers)
            response.raise_for_status()
        # catch any errors
        except Exception as e:
            # update TABLE_DATA status and message
            TABLE_DATA[self.session][1] = "[red]FAILED"
            # error message with url
            TABLE_DATA[self.session][5] =  "[white]@" + base_url.replace("https://musicbox.acom.ucar.edu/musicbox/api/", "").replace("/", " ") + " [red]" + str(e).replace("for url: " + base_url, "")
            # update table
            updateTable()
            success = False
            self.should_stop = True
            return (response, time.time() - start_time, success)
        # return the time it took and whether it was successful
        return (response, time.time() - start_time, success)
    # set example using api call
    def setExample(self, example):
        # make api call
        base_url = "https://musicbox.acom.ucar.edu/musicbox/api/load-example/?example=" + str(example)

        # make api call
        (response, time, success) = self.apiCall(base_url, "")
        # return the time it took and whether it was successful
        return (time, success)

    
    # get sessionid from api call
    def getRemoteUID(self):
        base_url = "https://musicbox.acom.ucar.edu/musicbox/api/check-load/"
        tmp_time = time.time()
        # make api call
        (response, timez, success) = self.apiCall(base_url, "")
        # turn response into json
        response = response.json()
        ac_time = time.time() - tmp_time
        # check if time is less than 1 second
        if ac_time < 1:
            # set to ms
            ac_time = ac_time * 1000
            ac_time = str(round(ac_time, 2)) + "ms"
        else:
            ac_time = str(round(ac_time, 2)) + "s"
        # if successful, get the sessionid from the cookie
        if success:
            # get sessionid from response
            self.uid = response["session_id"]
        # check if session_id is empty
        if self.uid == "":
            TABLE_DATA[self.session][1] = "[red]FAILED"
            TABLE_DATA[self.session][4] = "[red]" + str(ac_time)
            TABLE_DATA[self.session][5] =  "[white]@" + base_url.replace("https://musicbox.acom.ucar.edu/musicbox/api/", "").replace("/", " ") + " [red]Session UID is empty"
            updateTable()
            sys.exit(1)
        return self.uid

    # run model
    def runModel(self):
        base_url = "https://musicbox.acom.ucar.edu/musicbox/api/run/"
        (response, time, success) = self.apiCall(base_url, "")
        return (time, success)
    # check if model is done
    def isDone(self):
        tmp_time = time.time()
        base_url = "https://musicbox.acom.ucar.edu/musicbox/api/check-load/"
        # make api call
        (response, timez, success) = self.apiCall(base_url, "")
        # grab status from response
        response = response.json()
        if response["status"] == "done":
            # set tmp_time to original start time
            tmp_time = start_time
        # set message to response status for debugging
        # TABLE_DATA[self.session][5] = "[white]@" + base_url.replace("https://musicbox.acom.ucar.edu/musicbox/api/", "").replace("/", " ") + " Response: [#2be3ac]" + str(response)
        # calcate time it took to do everything by using start time
        ac_time = time.time() - tmp_time
        # check if time is less than 1 second
        if ac_time < 1:
            # set to ms
            ac_time = ac_time * 1000
            ac_time = str(round(ac_time, 2)) + "ms"
        else:
            # set to seconds
            ac_time = str(round(ac_time, 2)) + "s"
        if response["status"] == "done":
            self.done = True
            # update table
            TABLE_DATA[self.session][1] = "[#2be3ac]DONE!!"
            TABLE_DATA[self.session][4] = "[#2be3ac]" + str(ac_time)
            TABLE_DATA[self.session][5] = ""
            updateTable()
        else:
            # update time it took to make request
            TABLE_DATA[self.session][4] = "[magneta]" + str(ac_time)
        # return the time it took and whether it was successful
        return (ac_time, success, response["status"])

def updateTable():
    # reset table
    global table
    global currently_updating
    global TABLE_DATA
    # check if currently updating
    if currently_updating:
        return
    table = Table(show_header=True, header_style="bold magenta")
    # set title
    table.title = "MusicBox Load Tester"
    # set title style
    table.title_style = "bold #296a70"
    table.footer = "Please only run if you have permission to do so."
    table.add_column("Session #", justify="right", style="cyan", no_wrap=True)
    table.add_column("Status", justify="left", style="bold #fcba03") # status, unique color
    table.add_column("UID", justify="left", style="white")
    table.add_column("Example #", justify="center", style="white")
    table.add_column("Response/Run Time", justify="center", style="magenta")
    table.add_column("Message", justify="left", style="red")

    
   
    # add rows to via TABLE_DATA
    for row in TABLE_DATA:
        table.add_row(*row)
    
    live.start()
    live.update(table, refresh=True)
    currently_updating = False
# create session callback for threading
def finishedCreatingSession(session, future):
    # get result
    result = future.result()
    # check if successful by checking if the session id is empty
    if result == "":
        TABLE_DATA[session.session][1] = "[red]FAILED"
        TABLE_DATA[session.session][5] =  "[white]@" + result[1].replace("https://musicbox.acom.ucar.edu/musicbox/api/", "").replace("/", " ") + " [red]Session ID is empty"
        return
    
    # if successful, update table
    TABLE_DATA[session.session][1] = "[#2be3ac]PREPARING MODEL"
    TABLE_DATA[session.session][2] = result
    arg = random.randint(1, 3)
    TABLE_DATA[session.session][3] = str(arg)
    updateTable()
    # set example with pool and pass random example
    future2 = pool.submit(session.setExample, arg)
    # futures.append(future2)
    # set callback
    future2.add_done_callback(functools.partial(finishedSettingExample, session))

# set example callback for threading
def finishedSettingExample(session, future):
    # get result
    result = future.result()

# main interactive console code
if __name__ == "__main__":
    # arguments
    if len(sys.argv) < 2:
        print()
        # usage: session #, --wait (optional), --fixed-example (optional)
        print("Usage: python musicbox-destroyer.py <number of sessions> [--wait] [--fixed-example] [--run-asynchronously] [--ddos-mode]")
        # print more detailed usage
        print("Example: python musicbox-destroyer.py 20 --wait")
        # details on each argument
        print("""
        --wait: wait for each session to finish before exiting. Default is to exit as soon as all sessions are created but not necessarily finished.
        --fixed-example: use the same example for each session (default is to use a random example)
        --run-asynchronously: run each session in a separate thread (default is to run each session sequentially). This is useful for testing the server's ability to handle multiple sessions at once (load testing), but it will not give you an accurate idea of how long it takes to run a single session.
        --ddos-mode: can be run in asynchronous or synchronous mode. Once sessions are done running in this mode they'll be restarted from the beginning. This is useful for testing the server's ability to handle a large number of sessions at once (DDoS testing). To stop the script, press CTRL+C, otherwise it'll run forever. For this mode the <number of sessions> will indicate how many should run at a time, however, the script will keep creating new sessions until you stop it.
        """)

        sys.exit(1)
     # clear screen on all platforms
    os.system('cls' if os.name == 'nt' else 'clear')
    #################CONFIGURATION#################
    num_sessions = int(sys.argv[1])
    pool = ThreadPoolExecutor(max_workers=num_sessions, thread_name_prefix="MusicBox-Session-")
    sessions = []
    run_times = []
    actual_times = []
    failed_sessions = 0
    run_asynchronously = False
    if "--run-asynchronously" in sys.argv:
        run_asynchronously = True
    wait = False
    if "--wait" in sys.argv:
        wait = True
    fixed_example = False
    if "--fixed-example" in sys.argv:
        fixed_example = True
    ###############################################
    # add rows
    for i in range(num_sessions):
        # update TABLE_DATA
        TABLE_DATA.append([str(i + 1), "Creating..", ".", ".", "", ""])
    # refresh table
    updateTable()

    #################ASYNCHRONOUS SESSIONS#################
    if run_asynchronously:
        # 1) create all sessions in separate threads at the same time
        # 2) once a session is created, move on to the next step of setExample
        # 3) once a session has setExample, move on to the next step of runModel
        # 4) once a session has runModel, move on to the next step of isDone (if --wait is specified)

        
        # create sessions using thread pool
        for i in range(num_sessions):
            session = MusicBoxSession("", i)
            future = pool.submit(session.getRemoteUID)
            # futures.append(future)
            # add callback and args
            future.add_done_callback(functools.partial(finishedCreatingSession, session)) # session is passed as an argument to finishedCreatingSession
    ######################################################

    #################SEQUENTIAL SESSIONS#################
    else:
        # create sessions
        for i in range(num_sessions):
            # create session
            session = MusicBoxSession("", i)
            # get sessionid
            uid = session.getRemoteUID()
            # print out percentage using progress bar using rich
            

            # check if uid is valid
            if uid == "":
                # update TABLE_DATA
                TABLE_DATA[i][1] = "[red]FAILED"
                TABLE_DATA[i][5] = "[red]Could not create session (server may be down)"

                # refresh table
                updateTable()
                continue

            # add to list
            sessions.append(session)
            # update table
            TABLE_DATA[i][1] = "[#2be3ac]CREATED"
            TABLE_DATA[i][2] = str(uid)

            # refresh table
            updateTable()

        i = 1
        # set example
        for session in sessions:
            if TABLE_DATA[i - 1][1] == "[red]FAILED":
                i += 1
                failed_sessions += 1
                continue
            tmp_time = time.time()
            # random number between 1 and 3
            num = random.randint(1, 3)
            # set example
            timez, success = session.setExample(num)
            ac_time = time.time() - tmp_time
            # check if time is less than 1 second
            if ac_time < 1:
                # set to ms
                ac_time = ac_time * 1000
                ac_time = str(round(ac_time, 2)) + "ms"
            else:
                ac_time = str(round(ac_time, 2)) + "s"
            if success:
                # update table
                TABLE_DATA[i - 1][1] = "PREPARING EXAMPLE"
                TABLE_DATA[i - 1][4] = str(ac_time)
                TABLE_DATA[i - 1][3] = str(num)
                # refresh table
                updateTable()
            else:
                # update table
                TABLE_DATA[i - 1][1] = "[red]FAILED"
                # TABLE_DATA[i - 1][5] = "[red]Could not set example (server may be down)"
                # refresh table
                updateTable()
                failed_sessions += 1
            i += 1
        i = 1
        # run model
        for session in sessions:
            tmp_time = time.time()
            # only run model if example was set successfully
            # check TABLE_DATA for failed message
            if TABLE_DATA[i - 1][1] == "[red]FAILED" or session.should_stop:
                i += 1
                failed_sessions += 1
                continue
            # init run model (may take longer to actually run)
            timez, success = session.runModel()
            ac_time = time.time() - tmp_time
            # check if time is less than 1 second
            if ac_time < 1:
                # set to ms
                ac_time = ac_time * 1000
                ac_time = str(round(ac_time, 2)) + "ms"
            else:
                # set to seconds
                ac_time = str(round(ac_time, 2)) + "s"
            run_times.append(timez)
            actual_times.append(timez)
            if success == False:
                failed_sessions += 1
            else:
                # update table
                TABLE_DATA[i - 1][1] = "RUNNING MODEL"
                TABLE_DATA[i - 1][4] = str(ac_time)
                # refresh table
                updateTable()
            i += 1
    ######################################################
    # now check if we should wait for all sessions to finish
    if "--wait" in sys.argv:
        # asynchronously check if all sessions are done
        i = 0
        # list of threads
        threads = []
        while True:
            # asynchronously check if all sessions are done
            for session in sessions:
                if session.done or session.should_stop:
                    continue
                # create thread
                t = threading.Thread(target=session.isDone)
                # add to list
                threads.append(t)
                # start thread
                t.start()
            # wait for all threads to finish
            for t in threads:
                t.join()
            # check if all sessions are done by checking output of isDone() for 'done'
            all_done = True
            for i, session in enumerate(sessions):
                # grab response from isDone() ran in thread
                if session.done == False and session.should_stop == False:
                    # update table
                    TABLE_DATA[i][1] = "[#2be3ac]WAITING"
                    all_done = False
                elif session.done == True and session.should_stop == False:
                    # update table
                    TABLE_DATA[i][1] = "[green]DONE!!"
                    
                    i += 1
            updateTable()
            # if all sessions are done, break
            if all_done:
                break
            # sleep before checking again
            time.sleep(5)
