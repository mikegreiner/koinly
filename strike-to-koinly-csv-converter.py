import csv
import sys

# Strike format:
# Transaction ID,Initiated Time (UTC),Completed Time (UTC), Transaction Type,State,Amount 1,Currency 1,Amount 2,Currency 2,Balance 1,Currency 1,Balance - BTC,Destination,Description
# 0456418c-00ac-4c15-8fb0-cfe8c4c48b74,Jan 01 2022 00:41:59,Trade,Completed,-1.00,USD,0.00002144,BTC,85.00,USD,0.01331688,,
#
# Strike format 2024:
#
# Transaction ID,Initiated Date (UTC),Initiated Time (UTC),Completed Time (UTC),Completed Time (UTC),Transaction Type,State,Amount 1,Currency 1,Fee 1,Amount 2,Currency 2,Fee 2,BTC Price,Balance 1,Currency 1,Balance - BTC,Destination,Description
# b2a72d84-69c8-414e-b656-3ad378afbe31,Jun 28 2024,00:00:01,,,Deposit,Pending,10.00,USD,,,,,,,,,,
# b2a72d84-69c8-414e-b656-3ad378afbe31,Jun 28 2024,00:00:01,Jun 28 2024,00:00:06,Deposit,Reversed,10.00,USD,,,,,,,,,,
# 809e1051-f8ea-4355-b75d-6367314e30f2,Jun 28 2024,00:04:43,Jul 03 2024,21:25:27,Deposit,Completed,10.00,USD,,,,,,10.81,USD,,,
#
# Note: Do we need to conver the negative numbers (-1.00) to their positive equivalent (absolute value)?
#
# Koinly universal format:
# Date,Sent Amount,Sent Currency,Received Amount,Received Currency,Fee Amount,Fee Currency,Net Worth Amount,Net Worth Currency,Label,Description,TxHash
# Jan 01 2022 00:41:59,-1,USD,0.00002144,BTC,,,,,,,
#
# See: https://help.koinly.io/en/articles/3662999-how-to-create-a-custom-csv-file-with-your-data

if len(sys.argv) != 2:
    print('ERROR: Please enter a single input filename to convert')
    sys.exit(-1)

inputCsv = sys.argv[1]

# Print the Koinly headers
print('Date,Sent Amount,Sent Currency,Received Amount,Received Currency,Fee Amount,Fee Currency,Net Worth Amount,Net Worth Currency,Label,Description,TxHash');

with open(inputCsv, newline='') as strikeCsvFile:
    reader = csv.DictReader(strikeCsvFile)
    for row in reader:
        # Only process completed (successful) trades
        if row['State'] == 'Completed':
            if row['Transaction Type'] == 'Trade':
                print(row['Completed Time (UTC)'], row['Amount 1'], row['Currency 1'], row['Amount 2'], row['Currency 2'], '', '', '', '', '', 'Trade|Strike transaction: ' + row['Transaction ID'], '', sep=',')
            elif row['Transaction Type'] == 'Deposit':
                print(row['Completed Time (UTC)'], '', '', row['Amount 1'], row['Currency 1'], '', '', '', '', '', 'Deposit|Strike transaction: ' + row['Transaction ID'], '', sep=',')
            elif row['Transaction Type'] == 'Withdrawal':
                print(row['Completed Time (UTC)'], row['Amount 2'], row['Currency 2'], '', '', '', '', '', '', '', 'Withdrawal|Strike transaction: ' + row['Transaction ID'], '', sep=',')
            elif row['Transaction Type'] == 'Lightning':
                print(row['Completed Time (UTC)'], row['Amount 1'], row['Currency 1'], '', '', '', '', '', '', '', 'Withdrawal|Strike transaction: ' + row['Transaction ID'], '', sep=',')
            else:
                print('ERROR: Unknown transaction type:', row['Transaction Type'])
                print('      ', row)
