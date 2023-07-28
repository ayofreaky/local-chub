import os, json
from flask import Flask, render_template, request, send_from_directory

app = Flask(__name__)

CARDS_PER_PAGE = 50
CARD_PREVIEW_SIZE = (300, 300)

def getCardMetadata(cardId):
    metadataFile = os.path.join('static', f'{cardId}.json')
    with open(metadataFile) as f:
        metadata = json.load(f)
    return metadata

def createCardEntry(metadata):
    imagePath = f'static/{metadata["id"]}.png'
    return {
        'author': metadata['fullPath'].split('/')[0],
        'name': metadata['name'],
        'tagline': metadata['tagline'],
        'description': metadata['description'].replace("Creator's notes go here.", '\n'),
        'topics': metadata['topics'],
        'imagePath': imagePath
    }

def getCardList(page, search_query=None):
    cards = []
    files = os.listdir('static')

    if search_query:
        for file in files:
            if file.endswith('.json'):
                cardId = file.split('.')[0]
                metadata = getCardMetadata(cardId)
                if 'author:' in search_query and search_query.split(':')[-1].lower() in metadata['fullPath'].split('/')[0].lower():
                    cards.append(createCardEntry(metadata))
                elif 'tag:' in search_query and search_query.split(':')[-1].lower() in [tag.lower() for tag in metadata['topics']]:
                    cards.append(createCardEntry(metadata))
                elif metadata and (search_query.lower() in metadata['name'].lower() or search_query.lower() in metadata['tagline'].lower() or search_query.lower() in metadata['description'].lower() or search_query.lower() in ' '.join(metadata['topics']).lower()):
                    cards.append(createCardEntry(metadata))
    else:
        startIndex = (page - 1) * CARDS_PER_PAGE
        endIndex = startIndex + CARDS_PER_PAGE
        for file in files[startIndex:endIndex]:
            if file.endswith('.json'):
                cardId = file.split('.')[0]
                metadata = getCardMetadata(cardId)
                if metadata:
                    cards.append(createCardEntry(metadata))

    return cards

@app.route('/static/<path:filename>', methods=['GET'])
def image(filename):
    return send_from_directory('static', filename)

@app.route('/', methods=['GET'])
def index():
    page = int(request.args.get('page', 1))
    search_query = request.args.get('search_query')
    cards = getCardList(page, search_query)

    search_results = None
    if search_query:
        search_results = [card for card in cards]

    return render_template('index.html', cards=cards, page=page, card_preview_size=CARD_PREVIEW_SIZE, search_results=search_results)

if __name__ == '__main__':
    app.run(debug=True, port=1488)