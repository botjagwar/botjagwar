def to_malagasy_month(month):
    months = {
        1: 'Janoary',
        2: 'Febroary',
        3: 'Martsa',
        4: 'Aprily',
        5: 'Mey',
        6: 'Jona',
        7: 'Jolay',
        8: 'Aogositra',
        9: 'Septambra',
        10: 'Oktobra',
        11: 'Novambra',
        12: 'Desambra'
    }
    return months.get(month, 'Tsy fantatra')

def dataframe_to_wikitable(df):
    """
    Convert a pandas DataFrame to a Wikipedia table.

    Parameters:
    df (pd.DataFrame): The DataFrame to convert.

    Returns:
    str: A string representing the DataFrame in Wikipedia table format.
    """
    table = '{| class="wikitable sortable" style="text-align: center;"\n'

    # Add the header row
    table += '! ' + ' !! '.join(df.columns) + '\n'

    # Add the data rows
    for index, row in df.iterrows():
        table += '|-\n'
        table += '| ' + ' || '.join(row.astype(str)) + '\n'

    table += '|}'
    return table