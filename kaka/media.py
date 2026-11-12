"""Curadoria de fotografias ilustrativas. Créditos e fontes em IMAGE-CREDITS.md."""
def photo(ident, width=1000):
    return f'https://images.pexels.com/photos/{ident}/pexels-photo-{ident}.jpeg?auto=compress&cs=tinysrgb&w={width}&q=80'

HERO = photo(6969032, 1800)
PROCESS = photo(6870296, 1200)
IMAGES = {
    'lavagem-detalhada': (6873191, 'Lavagem com espuma em um carro preto'),
    'polimento-tecnico': (6870296, 'Politriz trabalhando a superfície de um veículo'),
    'protecao-de-pintura': (6872176, 'Limpeza cuidadosa da carroceria com uma esponja'),
    'higienizacao-interna': (31390691, 'Limpeza do volante e das superfícies internas'),
    'vitrificacao': (6969032, 'Reflexos na pintura de um carro preto em uma oficina'),
    'revitalizacao-de-plasticos': (20042050, 'Produtos e equipamentos para acabamento automotivo'),
    'detalhamento-de-rodas': (5628263, 'Limpeza manual de uma roda automotiva'),
}
GALLERY = [
    (photo(6873191), 'Lavagem por etapas', 'Lavagem'),
    (photo(6870296), 'Precisão no polimento', 'Polimento'),
    (photo(31390691), 'Cuidado com o interior', 'Higienização'),
    (photo(6872176), 'Preparação da superfície', 'Proteção'),
    (photo(6969032), 'Reflexos e acabamento', 'Vitrificação'),
    (photo(5628263), 'Atenção às rodas', 'Detalhes'),
]
