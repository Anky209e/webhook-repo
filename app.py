from flask import Flask, json,request, jsonify
from flask import render_template
from datetime import datetime,timezone
from pymongo import MongoClient

app = Flask(__name__)
# Running locally in docker
client = MongoClient("mongodb://localhost:27017/")
db = client['webhooks']
collection = db['events']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/github', methods=['POST'])
def github_webhook():
    """
        Handle incoming GitHub webhooks for push and pull request events.
        Store relevant data in MongoDB.
    """
    if request.method == 'POST':
        event = request.headers.get('X-GitHub-Event')
        payload = request.json
        if payload:
            # Storing relevant data from the payload
            data = {
                "author": payload['sender']['login'],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "repository": payload['repository']['name'],
                "repository_url": payload['repository']['html_url'],
                "commit_id": payload.get('head_commit', {}).get('id', 'N/A'),
                "commit_message": payload.get('head_commit', {}).get('message', 'N/A'),
                "action_type": event.upper(),
                "from_branch": None,
                "to_branch": None
            }

            # Determine branches based on event type
            if event == 'push':
                data["to_branch"] = payload['ref'].split('/')[-1]
            elif event == 'pull_request':
                data["from_branch"] = payload['pull_request']['head']['ref']
                data["to_branch"] = payload['pull_request']['base']['ref']
                if payload['action'] == 'closed' and payload['pull_request']['merged']:
                    data["action_type"] = 'MERGE'
                else:
                    data["action_type"] = 'PULL_REQUEST'
            
            # Insert data into MongoDB
            collection.insert_one(data)
            data.pop('_id', None) 
            print(data)
            return jsonify({"status": "success", "message": "Webhook received","data":data}), 200
        else:
            return jsonify({"status": "error", "message": "No data received"}), 400
    else:
        return jsonify({"status": "error", "message": "Invalid request method"}), 405


# Route to retrieve events
@app.route('/events')
def get_events():
    """
        Retrieve the last 10 events from the database and format them for display.
    """
    events = collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(10)
    output = []

    for e in events:
        dt = datetime.fromisoformat(e["timestamp"].replace("Z", ""))
        formatted_time = dt.strftime("%d %B %Y - %I:%M %p UTC")

        # Generate the message based on event type
        if e["action_type"] == "PUSH":
            if not e.get("to_branch"):
                message = f'{e["author"]} pushed to the repository {e["repository"]} on {formatted_time}'
            else:
                message = f'{e["author"]} pushed to {e["to_branch"]} on {formatted_time}'

        elif e["action_type"] == "PULL_REQUEST":
            message = f'{e["author"]} submitted a pull request from {e["from_branch"]} to {e["to_branch"]} on {formatted_time}'

        elif e["action_type"] == "MERGE":
            if not e.get("from_branch") or not e.get("to_branch"):
                message = f'{e["author"]} merged a pull request on {formatted_time}'
            else:
                message = f'{e["author"]} merged branch {e["from_branch"]} to {e["to_branch"]} on {formatted_time}'

        else:
            message = "Unknown event"

        output.append({
            "author": e.get("author"),
            "timestamp": formatted_time,
            "repository": e.get("repository"),
            "repository_url": e.get("repository_url"),
            "commit_id": e.get("commit_id"),
            "commit_message": e.get("commit_message"),
            "action_type": e.get("action_type"),
            "from_branch": e.get("from_branch"),
            "to_branch": e.get("to_branch"),
            "message": message
        })

    return jsonify(output)

if __name__ == '__main__':
    app.run(debug=True)