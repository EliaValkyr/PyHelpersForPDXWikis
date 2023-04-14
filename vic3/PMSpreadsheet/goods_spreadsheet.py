from vic3.game import vic3game
from vic3.vic3lib import Good

goods: dict[str, Good] = vic3game.parser.goods


def get_goods_order() -> list[Good]:
    # Sort goods by category, then by file order.
    goods_category_order: list[str] = ['staple', 'industrial', 'luxury', 'military']
    assert set(good.category for good in goods.values()) == set(goods_category_order)
    return [good for category in goods_category_order for good in goods.values() if good.category == category]


def print_goods_data(dir_name: str) -> None:
    file_name = dir_name / "goods.txt"
    file = open(file_name, 'w')

    headers: list[str] = [
        'Name',
        'Display Name',
        'Category',
        'Price',
    ]

    print(
        *headers,
        sep='\t',
        file=file
    )

    for good in get_goods_order():

        print(
            good.name,
            good.display_name,
            good.category,
            good.cost,
            sep='\t',
            file=file
        )



