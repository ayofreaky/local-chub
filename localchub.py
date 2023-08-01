import os, json, base64, requests
from flask import Flask, render_template, request, send_from_directory, jsonify, Response
from PIL import Image, UnidentifiedImageError

app = Flask(__name__)

CARDS_PER_PAGE = 50
CARD_PREVIEW_SIZE = (300, 300)

def getCardMetadata(cardId):
    metadataFile = os.path.join('static', f'{cardId}.json')
    with open(metadataFile) as f:
        metadata = json.load(f)
    return metadata

def getPngInfo(cardId):
    with open(f'static/{cardId}.png', 'rb') as f:
        img = Image.open(f)
        return json.loads(base64.b64decode(img.png.im_info['chara']).decode('utf-8'))

def pngCheck(cardId):
    try:
        Image.open(f'static/{cardId}.png').format == 'PNG'
        return True
    except UnidentifiedImageError:
        return False

def createCardEntry(metadata):
    return {
        'id': metadata['id'],
        'author': metadata['fullPath'].split('/')[0],
        'name': metadata['name'],
        'tagline': metadata['tagline'],
        'description': metadata['description'].replace("Creator's notes go here.", '\n'),
        'topics': [topic for topic in metadata['topics'] if topic != 'ROOT'],
        'imagePath': f'static/{metadata["id"]}.png',
        'tokenCount': metadata['nTokens']
    }

def getCardList(page, search_query=None):
    cards = []
    cardIds = sorted([int(file.split('.')[0]) for file in os.listdir('static') if file.lower().endswith('.png')], reverse=True)

    if search_query:
        for cardId in cardIds:
            metadata = getCardMetadata(cardId)
            if 'author:' in search_query and search_query.split(':')[-1].lower() in metadata['fullPath'].split('/')[0].lower():
                cards.append(createCardEntry(metadata))
            elif 'tag:' in search_query and all(tag.strip() in [tag.lower() for tag in metadata['topics']] for tag in search_query.split(':')[-1].lower().split(',')):
                cards.append(createCardEntry(metadata))
            elif 'title:' in search_query and search_query.split(':')[-1].lower() in metadata['name'].split('/')[0].lower():
                cards.append(createCardEntry(metadata))
            elif metadata and all(query.strip().lower() in metadata['name'].lower() or query.strip().lower() in metadata['tagline'].lower() or query.strip().lower() in metadata['description'].lower() or query.strip().lower() in [tag.lower() for tag in metadata['topics']] for query in search_query.lower().split(',')):
                cards.append(createCardEntry(metadata))
    else:
        startIndex = (page - 1) * CARDS_PER_PAGE
        endIndex = startIndex + CARDS_PER_PAGE
        for cardId in cardIds[startIndex:endIndex]:
            metadata = getCardMetadata(cardId)
            if metadata:
                cards.append(createCardEntry(metadata))

    return cards

def blacklistAdd(cardId):
    if not os.path.exists('blacklist.txt'):
        with open('blacklist.txt', 'w') as f:
            f.write('')
    with open('blacklist.txt', 'a') as f:
        f.write(f'{cardId}\n')

def blacklistCheck(cardId):
    if os.path.exists('blacklist.txt'):
        with open('blacklist.txt', 'r') as f:
            return cardId in f.read().split('\n')
    return False

@app.route('/static/<path:filename>', methods=['GET'])
def image(filename):
    return send_from_directory('static', filename)

@app.route('/get_png_info/<cardId>', methods=['GET'])
def get_png_info(cardId):
    png_info = getPngInfo(cardId)
    return jsonify(png_info)

@app.route('/', methods=['GET'])
def index():
    page = int(request.args.get('page', 1))
    search_query = request.args.get('search_query')
    cards = getCardList(page, search_query)

    search_results = None
    if search_query:
        search_results = [card for card in cards]

    return render_template('index.html', cards=cards, page=page, card_preview_size=CARD_PREVIEW_SIZE, search_results=search_results)

@app.route('/sync', methods=['GET'])
def syncCards():
    cardIds = sorted([int(file.split('.')[0]) for file in os.listdir('static') if file.lower().endswith('.png')], reverse=True)
    totalCards, currCard, newCards = 500, 0, 0
    def dlCard(card):
        nonlocal newCards, currCard
        cardId = card['id']
        if cardId not in cardIds:
            with open(f'static/{cardId}.json', 'w', encoding='utf-8') as f:
                f.write(json.dumps(card, indent=4))
            with open(f'static/{cardId}.png', 'wb') as f:
                f.write(requests.get(f'https://avatars.charhub.io/avatars/{card["fullPath"]}/chara_card_v2.png').content)
                print(f'Downloading {card["name"]} ({cardId})..')
            if not pngCheck(cardId):
                for ext in ['png', 'json']:
                    os.remove(f'static/{cardId}.{ext}')
                blacklistAdd(cardId)
                return False
            newCards += 1
        currCard += 1
        return True

    def genSyncData():
        page = 1
        while currCard < totalCards:
            r = requests.get('https://v2.chub.ai/search', params={'first': totalCards, 'page': f'{page}', 'sort': 'created_at', 'venus': 'false', 'asc': 'false', 'nsfw': 'true'}).json()
            cards = r['data']['nodes']
            for card in cards:
                if not blacklistCheck(str(card['id'])):
                    result = dlCard(card)
                    if not result:
                        continue
                    progress = (currCard / totalCards) * 100
                    cardName = card['name']
                    respData = {'progress': progress, 'currCard': cardName, 'newCards': newCards}
                    yield f"data: {json.dumps(respData)}\n\n"
            page += 1

        respData = {'progress': 100, 'currCard': 'Sync Completed', 'newCards': newCards}
        yield f"data: {json.dumps(respData)}\n\n"

    return Response(genSyncData(), content_type='text/event-stream')

@app.route('/delete_card/<int:cardId>', methods=['POST', 'DELETE'])
def delete_card(cardId):
    try:
        for ext in ['png', 'json']:
            os.remove(f'static/{cardId}.{ext}')
        blacklistAdd(cardId)
        return jsonify({'message': 'Card deleted successfully'}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=1488)