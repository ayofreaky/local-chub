import os, json, base64, requests, re, random
from flask import Flask, render_template, request, send_from_directory, jsonify, Response
from PIL import Image, UnidentifiedImageError

app = Flask(__name__)

CARDS_PER_PAGE = 50
CARD_PREVIEW_SIZE = (300, 300)

def getCardMetadata(cardId):
    with open(f'static/{cardId}.json', 'r', encoding='utf-8') as f:
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
        'description': metadata['description'].replace('Creator\'s notes go here.', '\n'),
        'topics': [topic for topic in metadata['topics'] if topic != 'ROOT'],
        'imagePath': f'static/{metadata["id"]}.png',
        'tokenCount': metadata['nTokens']
    }

def getCardList(page, query=None, searchType='basic'):
    cards = []
    cardIds = sorted([int(file.split('.')[0]) for file in os.listdir('static') if file.lower().endswith('.png')], reverse=True)
    count = len(cardIds)

    if query:
        for cardId in cardIds:
            metadata = getCardMetadata(cardId)

            if searchType == 'tag' and all(tag.strip() in [tag.lower() for tag in metadata['topics']] for tag in query.lower().split(',')):
                cards.append(createCardEntry(metadata))
            elif searchType == 'author' and query.strip().lower() == metadata['fullPath'].split('/')[0].lower():
                cards.append(createCardEntry(metadata))
            elif searchType == 'title' and query.strip().lower() in metadata['name'].lower():
                cards.append(createCardEntry(metadata))
            elif searchType == 'random':
                cnt = int(re.search(r'\d+', query)[0]) if re.search(r'\d+', query) else 10
                for i in range(cnt):
                    [cards.append(createCardEntry(getCardMetadata(random.choice(cardIds))))]
                break
            elif searchType == 'basic' and all(query.strip().lower() in metadata['name'].lower() or query.strip().lower() in metadata['tagline'].lower() or query.strip().lower() in metadata['description'].lower() or query.strip().lower() in [tag.lower() for tag in metadata['topics']] for query in query.lower().split(',')):
                cards.append(createCardEntry(metadata))

    else:
        startIndex = (page - 1) * CARDS_PER_PAGE
        endIndex = startIndex + CARDS_PER_PAGE
        for cardId in cardIds[startIndex:endIndex]:
            metadata = getCardMetadata(cardId)
            if metadata:
                cards.append(createCardEntry(metadata))

    return cards, count

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
    query = request.args.get('query')
    searchType = request.args.get('type')
    cards, count = getCardList(page, query, searchType)

    search_results = None
    if query:
        search_results = [card for card in cards]

    return render_template('index.html', cards=cards, page=page, card_preview_size=CARD_PREVIEW_SIZE, search_results=search_results, count=count)

@app.route('/sync', methods=['GET'])
def syncCards():
    totalCards, currCard, newCards = int(request.args.get('c', 500)), 0, 0
    cardIds = sorted([int(file.split('.')[0]) for file in os.listdir('static') if file.lower().endswith('.png')], reverse=True)

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
        nonlocal totalCards
        page = 1
        r = requests.get('https://v2.chub.ai/search', params={'first': totalCards, 'page': f'{page}', 'sort': 'created_at', 'venus': 'false', 'asc': 'false', 'nsfw': 'true', 'min_tokens': '50'}).json()
        cards = r['data']['nodes']
        for card in cards:
            yield f"data: {json.dumps({'progress': round((currCard / len(cards)) * 100, 2), 'currCard': card['name'], 'newCards': newCards})}\n\n"
            if not blacklistCheck(str(card['id'])):
                if card['id'] == 88:
                    continue
                if not dlCard(card):
                    continue

        yield f"data: {json.dumps({'progress': 100, 'currCard': 'Sync Completed', 'newCards': newCards})}\n\n"

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

@app.route('/edit_tags/<int:cardId>', methods=['POST'])
def edit_tags(cardId):
    try:
        newTags = request.form.get('tags')
        metadata = getCardMetadata(cardId)
        metadata['topics'] = [tag.strip() for tag in newTags.split(',') if tag != '']
        with open(f'static/{cardId}.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4)
        return jsonify({'message': 'Tags updated successfully'}), 200
    except Exception as e:
        return jsonify({'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=1488)