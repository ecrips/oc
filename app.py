#!/usr/bin/python3

import asyncio
import websockets
import json
import random

clients = set()
admins = set()
blobs = {}
roundInfo = {}
roundName = ''

answers = open("answerlog.txt", "a")

teams = {}

async def register(websocket):
    clients.add(websocket)
    await broadcast()

async def unregister(websocket):
    clients.remove(websocket)
    if websocket in admins:
        admins.remove(websocket)
    await broadcast()

async def registerAdmin(websocket):
    admins.add(websocket)
    await adminbroadcast()

async def clearBlobs():
    global blobs

    blobs = {}
    for socket in clients:
        await socket.send(json.dumps({'action':'clearBlobs'}))

async def adminbroadcast():
    connections = len(clients)
    for socket in admins:
        await socket.send(json.dumps({
            'action': 'adminInfo',
            'teamInfo': teams,
            'connections': connections
            }))

async def broadcast():
    teamInfo = {}
    connections = len(clients)
    for k in teams.keys():
        team = teams[k]
        teamInfo[k] = {'connections':team['connections'],
                'score': team['score'],
                'correct': team['correct']}
    for socket in sorted(clients, key=lambda x:random.random()):
        if socket in admins:
            continue
        try:
            await socket.send(json.dumps({
                'action': 'info',
                'teamInfo': teamInfo,
                'connections': connections,
                'round': roundInfo
                }))
        except Exception:
            print("Send failed in broadcast :(")
    await adminbroadcast()

    with open("teaminfo.json","w") as f:
        json.dump(teams, f)

async def oc(websocket, path):
    global roundInfo
    global roundName

    teamName = None
    await register(websocket)
    print("New connection",websocket)
    try:
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            if data['action'] == "join":
                if teamName != None:
                    print("Attempt to join team when already in a team!")
                    break
                teamName = data['name']
                print("Connection joining team",teamName)
                if teamName not in teams:
                    teams[teamName] = {'connections': 1, 'score': 0, 'info':{},
                            'correct':0}
                else:
                    teams[teamName]['connections'] += 1
                await broadcast()
            elif data['action'] == "admin":
                await registerAdmin(websocket)
            elif data['action'] == "round":
                roundInfo = data['round']
                if 'name' in data:
                    roundName = data['name']
                await broadcast()
            elif data['action'] == "info":
                if teamName == None:
                    continue
                teams[teamName]['info'] = data['info']
                print(teamName,roundName,data['info'])
                if 'answer' in data['info']:
                    answers.write("%s,%s,%s,%s\n" % (roundName, teamName, data['info']['answer'], data['info']['clueNumber']))
                    answers.flush()
                await adminbroadcast()
            elif data['action'] == "clearBlobs":
                print("Clearing blobs")
                for k in teams.keys():
                    teams[k]['correct'] = 0
                await clearBlobs()
            elif data['action'] == "makeBlob":
                id = data['id']
                print("Receiving blob",id)
                blob = await websocket.recv()
                blobs[id] = blob
            elif data['action'] == "getBlob":
                id = data['id']
                print("Sending blob",id)
                await websocket.send(json.dumps({
                    'action': 'setBlob',
                    'id': id
                    }))
                await websocket.send(blobs[id])
            elif data['action'] == "deleteTeam":
                del teams[data['name']]
                await broadcast()
            elif data['action'] == "setScore":
                teams[data['name']]['score'] = int(data['score'])
                teams[data['name']]['correct'] = data['correct']
                await broadcast()
            elif data['action'] == "scoreAdd":
                if teamName == None:
                    continue
                teams[teamName]['score'] += int(data['amt'])
                await broadcast()
            else:
                print("Unknown action",data['action'])
    except websockets.exceptions.ConnectionClosed:
        print("ConnectionClosed")
    finally:
        print("Disconnecting",websocket)
        if teamName != None:
            teams[teamName]['connections'] -= 1
        await unregister(websocket)

try:
    with open("teaminfo.json") as f:
        teams = json.load(f)
    for i in teams.keys():
        teams[i]['connections'] = 0
    print("Loaded old team info")
except:
    pass

server = websockets.serve(oc, port = 8080)

asyncio.get_event_loop().run_until_complete(server)
asyncio.get_event_loop().run_forever()
