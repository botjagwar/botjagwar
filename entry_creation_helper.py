from api.output import WikiPageRendererFactory
from object_model.word import Entry

e = Entry(
        entry='test',
        part_of_speech='ana',
        entry_definition=[
            'socka', 'trial', 'some things you want to prove is good'
        ],
        language='an',
        etymology='From tesan',
        audio_pronunciations=['asdlkalkej'],
        references=['your mom', 'your dad'],
        examples=['I tested my own dick in her cunt. Was good']
    )

o = WikiPageRendererFactory('mg')()
s = o.render(e)
print(s, len(s))

