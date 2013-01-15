#!/usr/bin/env python

"""
Analyze parsed India trades data.
"""

import datetime, sys
import pandas

def rount_ceil_minute(d):
    """
    Round to nearest minute after the specified time.

    Parameters
    ----------
    d : datetime.datetime
       A time expressed using the `datetime.datetime` class.
       
    """
    
    return d-datetime.timedelta(seconds=d.second,
                                microseconds=d.microsecond,
                                minutes=(-1 if d.second != 0 or d.microsend != 0 else 0))


def sample(df, delta, date_time_col, *data_cols):
    """
    Sample data at a specific sampling time interval.

    Return a table of data containing at least two columns; one column contains times
    separated by the specified sampling interval, while the others contain the
    data points associated with the most recent times in the original table
    prior to each successive sampling time.
    
    Parameters
    ----------
    df : pandas.DataFrame
        Data to sample. Must contain columns with the names in `data_cols` and
        `date_time_col`.
    delta : datetime.timedelta
        Sampling interval.
    date_time_col : str
        Name of date/time.
    data_cols : tuple of str 
        Name(s) of data column.
        
    Returns
    -------
    out : pandas.DataFrame
        DataFrame containing column of resampled data points and sampling times.
        
    """

    # Uncomment to start and end at the nearest minute after the first and last
    # times in the input DataFrame:
    # t_min = round_ceil_minute(df[date_time_col].min())
    # t_max = round_ceil_minute(df[date_time_col].max())
    t_min = df[date_time_col].min()
    t_max = df[date_time_col].max()

    date = []
    data = []
    t = t_min
    temp_dict = {date_time_col: []}        
    last_dict = {}
    for col in data_cols:
        temp_dict[col] = []
        last_dict[col] = df.irow(0)[col]
    i = 1

    # Only update the data point stored at each time point when 
    # a time point in the original series is passed:
    while t < t_max:
        temp_dict[date_time_col].append(t)
        while t > df.irow(i)[date_time_col]:
            for col in data_cols:
                last_dict[col] = df.irow(i)[col]
            i += 1            
        for col in data_cols:
            temp_dict[col].append(last_dict[col])
        t += delta        
    return pandas.DataFrame(temp_dict)
    
def analyze(file_name):
    """
    Analyze parsed India data in specified file name.

    Parameters
    ----------
    file_name : str
        Name of CSV file containing parsed India data.
        
    Returns
    -------
    output : list
        Results of analysis. These include the following (in order):

        number of trades for Q1
        number of trades for Q2
        number of trades for Q3
        maximum trade price
        minimum trade price
        mean trade price
        number of trade interarrival times for Q1
        number of trade interarrival times for Q2
        number of trade interarrival times for Q3
        mean daily trade volume
        maximum daily trade volume
        minimum daily trade volume
        median daily trade volume

        mean trade price
        maximum daily price in bps (for each business day of 9/2012)
        minimum daily price in bps (for each business day of 9/2012)
        
    """

    df = pandas.read_csv(file_name, header=None, 
                         names=['record_indicator',
                                'segment',
                                'trade_number',
                                'trade_date',
                                'trade_time',
                                'symbol',
                                'instrument',
                                'expiry_date',
                                'strike_price',
                                'option_type',
                                'trade_price',
                                'trade_quantity',
                                'buy_order_num',
                                'buy_algo_ind',
                                'buy_client_id_flag',
                                'sell_order_num',
                                'sell_algo_ind',
                                'sell_client_id_flag'])    

    # Find number of trades below the quartiles:
    N_trade_price_q1 = len(df[df['trade_price'] < df['trade_price'].quantile(0.25)])
    N_trade_price_q2 = len(df[df['trade_price'] < df['trade_price'].quantile(0.50)])
    N_trade_price_q3 = len(df[df['trade_price'] < df['trade_price'].quantile(0.75)])

    # Other stats on the number of trades:
    max_trade_price = df['trade_price'].max()
    min_trade_price = df['trade_price'].min()
    mean_trade_price = df['trade_price'].mean()

    # Convert trade date/times to datetime.timedelta and join the column to the
    # original data:
    s_trade_date_time = \
      df[['trade_date', 'trade_time']].apply(lambda x: \
        datetime.datetime.strptime(x[0] + ' ' + x[1], '%m/%d/%Y %H:%M:%S.%f'),
          axis=1)
    s_trade_date_time.name = 'trade_date_time'
    df = df.join(s_trade_date_time)
    
    # Compute trade interarrival times for each day (i.e., the interval between
    # the last trade on one day and the first day on the following day should
    # not be regarded as an interarrival time):
    s_inter_time = df.groupby('trade_date')['trade_date_time'].apply(lambda x: x.diff())

    # Convert interarrival times to seconds; exclude the NaNs that result
    # because of the application of the diff() method to each group of trade
    # times:
    s_inter_time = \
      s_inter_time[s_inter_time.notnull()].apply(lambda x: x.total_seconds())                                                              
    
    # Find the interarrival times (XXX this is incorrect because it doesn't
    # leave out the intervals between the last trades on each day and the first
    # trades on each subsequent day XXX)
    #s_inter_time = s_trade_date_time.diff()[1:].apply(lambda x: x.total_seconds())

    # Find number of interarrival times below the quartiles:    
    N_inter_time_q1 = sum(s_inter_time<s_inter_time.quantile(0.25))
    N_inter_time_q2 = sum(s_inter_time<s_inter_time.quantile(0.50))
    N_inter_time_q3 = sum(s_inter_time<s_inter_time.quantile(0.75))

    # Compute the daily traded volume:
    s_daily_vol = df.groupby('trade_date')['trade_quantity'].apply(sum)
    daily_vol_list = s_daily_vol.tolist()
    mean_daily_vol = s_daily_vol.mean()
    max_daily_vol = s_daily_vol.max()
    min_daily_vol = s_daily_vol.min()
    median_daily_vol = s_daily_vol.median()

    # Sample trade prices every 3 minutes for each day of the month and combine
    # into a single DataFrame:
    df_trade_price_res = \
      df.groupby('trade_date').apply(lambda d: \
         sample(d, datetime.timedelta(minutes=3), 
                'trade_date_time', 'trade_price', 'trade_date'))

    # Compute standard deviation of sampled prices:
    std_trade_price = df_trade_price_res['trade_price'].std()

    # Compute average and standard deviation of returns in bps:
    s_returns = \
      df_trade_price_res.groupby('trade_date').apply( \
        lambda x: x['trade_price'].diff()/x['trade_price'])
    mean_returns = s_returns.mean()*10000
    std_returns = s_returns.std()*10000

    # Compute the average price trade for the entire month of data:
    mean_trade_price = df['trade_price'].mean()

    # Compute the daily maximum and minimum trade price expressed in basis
    # points away from the daily opening price:
    daily_price_max_list = map(lambda x: 10000*int(x),
      df.groupby('trade_date')['trade_price'].apply(max)-df.ix[0]['trade_price'])
    daily_price_min_list = map(lambda x: 10000*int(x),
      df.groupby('trade_date')['trade_price'].apply(min)-df.ix[0]['trade_price'])
    return df
     
if len(sys.argv) == 1:
    print 'need to specify input files'
    sys.exit(0)

df = analyze(sys.argv[1])    
# for file_name in sys.argv[1:]:
#     pass
