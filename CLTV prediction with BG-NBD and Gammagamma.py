##############################################################
# CLTV Prediction with BG-NBD and Gamma-Gamma Models
##############################################################

##############################################################
# 1. Business Problem
##############################################################

# FLO wants to determine a roadmap for its sales and marketing activities. In order for the company to plan
# the medium to long term, it is necessary to predict the potential value that existing customers will bring
# to the company in the future.

# Dataset Story
# The dataset consists of information obtained from the past shopping behaviors of customers who made their
# last purchases from FLO in 2020-2021 from OmniChannel (both online and offline shopping).

# Variables
# master_id -- Unique customer number
# order_channel -- Which channel is used for the purchase (Android, iOS, Desktop, Mobile)
# last_order_channel -- Channel used for the last purchase
# first_order_date -- Date of the customer's first purchase
# last_order_date -- Date of the customer's last purchase
# last_order_date_online -- Date of the customer's last online purchase
# last_order_date_offline -- Date of the customer's last offline purchase
# order_num_total_ever_online -- Total number of purchases made by the customer online
# order_num_total_ever_offline -- Total number of purchases made by the customer offline
# customer_value_total_ever_offline -- Total amount paid by the customer for offline purchases
# customer_value_total_ever_online -- Total amount paid by the customer for online purchases
# interested_in_categories_12 -- List of categories the customer shopped in the last 12 months

###############################################################
# 1 - Data Preparation
###############################################################
import datetime as dt
import pandas as pd
import matplotlib.pyplot as plt
from lifetimes import BetaGeoFitter
from lifetimes import GammaGammaFitter
from lifetimes.plotting import plot_period_transactions

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 100)
pd.set_option('display.float_format', lambda x: '%.4f' % x)
from sklearn.preprocessing import MinMaxScaler
# To scale the values between 0-1 or 0-100 for lifetime value

df_ = pd.read_csv('Datasets/flo_data_20k.csv')
df = df_.copy()
df.head()

# Data understanding
##############################################
def check_df(dataframe, head=5):
    print('################# Columns ################# ')
    print(dataframe.columns)
    print('################# Types  ################# ')
    print(dataframe.dtypes)
    print('##################  Head ################# ')
    print(dataframe.head(head))
    print('#################  Shape ################# ')
    print(dataframe.shape)
    print('#################  NA ################# ')
    print(dataframe.isnull().sum())
    print('#################  Quantiles ################# ')
    print(dataframe.describe([0, 0.05, 0.50, 0.95, 0.99]).T)
    print('')

check_df(df)

# Define the outlier_thresholds and replace_with_thresholds functions to suppress outliers
###########################################################################################
def outlier_thresholds(dataframe, variable):
    quartile1 = dataframe[variable].quantile(0.01)
    quartile3 = dataframe[variable].quantile(0.99)
    interquantile_range = quartile3 - quartile1
    up_limit = quartile3 + 1.5 * interquantile_range
    low_limit = quartile1 - 1.5 * interquantile_range
    return low_limit, up_limit

def replace_with_thresholds(dataframe, variable):
    low_limit, up_limit = outlier_thresholds(dataframe, variable)
    low_limit = round(low_limit)
    up_limit = round(up_limit)
    dataframe.loc[(dataframe[variable] < low_limit), variable] = low_limit
    dataframe.loc[(dataframe[variable] > up_limit), variable] = up_limit

# Suppress the outliers in the variables "order_num_total_ever_online", "order_num_total_ever_offline",
# "customer_value_total_ever_offline", "customer_value_total_ever_online".
#######################################################################################################
df.describe().T #--> as seen that, there are big defference between mean, %75 and max values of this 4 variables.
columns = ["order_num_total_ever_online", "order_num_total_ever_offline",
           "customer_value_total_ever_offline","customer_value_total_ever_online"]
for col in columns:
    replace_with_thresholds(df, col)

df.describe().T #--> after suppression max values decreased.

# Create new variables for the total number of purchases and total amount spent by omnichannel customers.
#########################################################################################################
df['order_num_total'] = df['order_num_total_ever_online'] + df['order_num_total_ever_offline']
df['customer_value_total'] = df['customer_value_total_ever_offline'] + df['customer_value_total_ever_online']

# Examine variable types. Convert the date variables to the date type.
######################################################################
date_columns = df.columns[df.columns.str.contains("date")]
df[date_columns] = df[date_columns].apply(pd.to_datetime)
df.dtypes

###############################################################
# 2 - Preparing Data for CLTV Calculation
###############################################################

# Take the date of the last purchase in the dataset as the analysis date, 2 days after.
########################################################################################
df["last_order_date"].max()
analysis_date = dt.datetime(2021, 6, 3)

# Create a new cltv dataframe containing customer_id, recency_cltv_weekly, T_weekly,
# frequency, and monetary_cltv_avg values.
####################################################################################
cltv = pd.DataFrame()
cltv["customer_id"] = df["master_id"]
cltv['recency_cltv_weekly'] = (df['last_order_date'] - df['first_order_date']).dt.days // 7
cltv['T_weekly'] = (analysis_date - df['first_order_date']).dt.days // 7
cltv['frequency'] = df['order_num_total']
cltv = cltv[(cltv['frequency'] > 1)]
cltv['monetary_cltv_avg'] = df['customer_value_total'] / cltv['frequency']
cltv.describe().T

###############################################################################
# 3. Calculating CLTV with BG/NBD and Gamma-Gamma Models
###############################################################################

# A. Predicting purchases using the BG/NBD model
################################################
# Fitting the BG/NBD model
######################
bgf = BetaGeoFitter(penalizer_coef=0.001)
bgf.fit(cltv['frequency'],
        cltv['recency_cltv_weekly'],
        cltv['T_weekly'])

# Predicting expected purchases for the next 3 months
###################################################
cltv["expected_sales_3_month"] = bgf.predict(4 * 3, cltv['frequency'],
                                             cltv['recency_cltv_weekly'],
                                             cltv['T_weekly'])
# Top 10 customers
cltv["expected_sales_3_month"].nlargest(10)

# Predicting expected purchases for the next 6 months
###################################################
cltv["expected_sales_6_month"] = bgf.predict(4 * 6, cltv['frequency'],
                                             cltv['recency_cltv_weekly'],
                                             cltv['T_weekly'])
# Top 10 customers
cltv["expected_sales_6_month"].nlargest(10)

# Plotting the transactional behavior
#####################################
plot_period_transactions(bgf)
plt.show(block=True)

# B. Predicting average value per transaction using the Gamma-Gamma model
#########################################################################

# Fitting the Gamma-Gamma model
###############################
ggf = GammaGammaFitter(penalizer_coef=0.01)
ggf.fit(cltv['frequency'], cltv['monetary_cltv_avg'])

# Calculating the expected average value per transaction
########################################################
cltv["exp_average_value"] = ggf.conditional_expected_average_profit(cltv['frequency'],
                                                                    cltv['monetary_cltv_avg'])
cltv.sort_values("exp_average_value", ascending=False).head(10)

# C. Calculating 6-month CLTV
#############################
CLTV = ggf.customer_lifetime_value(bgf, cltv['frequency'],
                                   cltv['recency_cltv_weekly'],
                                   cltv['T_weekly'],
                                   cltv['monetary_cltv_avg'],
                                   time=6, freq="W", discount_rate=0.01)

CLTV = CLTV.reset_index()
cltv_final = cltv.merge(CLTV, left_index=True, right_index=True, how='outer')

# Sorting the customers based on CLTV
#######################################################################
cltv_final.sort_values(by="clv", ascending=False).head(20)

###############################################################################
# 4. Creating Segments Based on CLTV Value
###############################################################################
# Divide all customers into 4 segments based on 6-month CLTV
#############################################################
cltv_final["segment"] = pd.qcut(cltv_final["clv"], 4, labels=["D", "C", "B", "A"])

cltv_final.sort_values(by="clv", ascending=False).head(10)

cltv_final.groupby("segment").agg({"count", "mean", "sum"})


# IMPORTANT NOTE: Assumptions of BG-NBD and Gamma-Gamma models:
# There should be no corr between Freq ve monetary,
# Freq should not ne float.
# Graphs are shown below:
cltv[['frequency','monetary_cltv_avg']].corr()
cltv["frequency"]=cltv["frequency"].astype(int)
plt.hist(cltv["frequency"])
plt.show(block=True)
cltv["frequency"].value_counts().sort_values(ascending=False)

# The function for all data process - includes all the steps above
def create_cltv_df(dataframe):
    # 1 - Data Preparation
    columns = ["order_num_total_ever_online", "order_num_total_ever_offline",
               "customer_value_total_ever_offline","customer_value_total_ever_online"]
    for col in columns:
        replace_with_thresholds(dataframe, col)
    dataframe["order_num_total"] = dataframe["order_num_total_ever_online"] + dataframe["order_num_total_ever_offline"]
    dataframe["customer_value_total"] = dataframe["customer_value_total_ever_offline"] + dataframe["customer_value_total_ever_online"]
    date_columns = dataframe.columns[dataframe.columns.str.contains("date")]
    dataframe[date_columns] = dataframe[date_columns].apply(pd.to_datetime)

    # 2 - Preparing Data for CLTV Calculation
    df["last_order_date"].max()
    analysis_date = dt.datetime(2021, 6, 3)
    cltv= pd.DataFrame()
    cltv["customer_id"] = dataframe["master_id"]
    cltv["recency_cltv_weekly"] = (dataframe["last_order_date"] - dataframe["first_order_date"]).dt.days // 7
    cltv["T_weekly"] = (analysis_date - dataframe["first_order_date"]).dt.days // 7
    cltv["frequency"] = dataframe["order_num_total"]
    cltv = cltv[(cltv['frequency'] > 1)]
    cltv["monetary_cltv_avg"] = dataframe["customer_value_total"] / cltv['frequency']
    # 3. Calculating CLTV with BG/NBD and Gamma-Gamma Models
    # Fitting the BG/NBD model
    bgf = BetaGeoFitter(penalizer_coef=0.001)
    bgf.fit(cltv['frequency'],
            cltv['recency_cltv_weekly'],
            cltv['T_weekly'])
    # Predicting expected purchases for the next 3 months
    cltv["expected_sales_3_month"] = bgf.predict(4 * 3, cltv['frequency'],
                                                 cltv['recency_cltv_weekly'],
                                                 cltv['T_weekly'])
       # Predicting expected purchases for the next 6 months
    cltv["expected_sales_6_month"] = bgf.predict(4 * 6, cltv['frequency'],
                                                 cltv['recency_cltv_weekly'],
                                                 cltv['T_weekly'])
    # Fitting the Gamma-Gamma model
    ggf = GammaGammaFitter(penalizer_coef=0.01)
    ggf.fit(cltv['frequency'], cltv['monetary_cltv_avg'])
    # Calculating the expected average value per transaction
    cltv["exp_average_value"] = ggf.conditional_expected_average_profit(cltv['frequency'],
                                                                        cltv['monetary_cltv_avg'])

    # Calculating 6-month CLTV
    CLTV = ggf.customer_lifetime_value(bgf, cltv['frequency'],
                                       cltv['recency_cltv_weekly'],
                                       cltv['T_weekly'],
                                       cltv['monetary_cltv_avg'],
                                       time=6, freq="W", discount_rate=0.01)
    CLTV = CLTV.reset_index()
    cltv_final = cltv.merge(CLTV, left_index=True, right_index=True, how='outer')
    # 4. Creating Segments Based on CLTV Value
    # Divide all customers into 4 segments based on 6-month CLTV
    cltv_final["segment"] = pd.qcut(cltv_final["clv"], 4, labels=["D", "C", "B", "A"])

    return cltv_final

cltv_final = create_cltv_df(df)
