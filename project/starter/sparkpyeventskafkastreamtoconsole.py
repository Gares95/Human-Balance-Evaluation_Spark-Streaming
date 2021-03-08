from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, unbase64, base64, split
from pyspark.sql.types import StructField, StructType, StringType, BooleanType, ArrayType, DateType

# Get the spark application object
spark = SparkSession.builder.appName("my-final-project").getOrCreate()
# Set the spark log level to WARN
spark.sparkContext.setLogLevel('WARN')

# Create a StructType for the Kafka stedi-events topic which has the Customer Risk JSON that comes from Redis- before Spark 3.0.0, schema inference is not automatic
stediEventJSONSchema = StructType(
    [
        StructField("customer", StringType()),
        StructField("score", StringType()),
        StructField("riskDate", StringType())
    ]
)

# Using the spark application object, read a streaming dataframe from the Kafka topic stedi-events as the source
# Be sure to specify the option that reads all the events from the topic including those that were published before you started the spark stream
stediEventsRawStreamingDF = spark.readStream\
    .format("kafka")\
    .option("kafka.bootstrap.servers", "localhost:9092")\
    .option("subscribe","stedi-events")\
    .option("startingOffsets","earliest")\
    .load()
# Cast the value column in the streaming dataframe as a STRING 
stediEventsStreamingDF = stediEventsRawStreamingDF.selectExpr("cast (key as string) key", "cast (value as string) value")
# Parse the JSON from the single column "value" with a json object in it, like this:
# +------------+
# | value      |
# +------------+
# |{"custom"...|
# +------------+
#
# and create separated fields like this:
# +------------+-----+-----------+
# |    customer|score| riskDate  |
# +------------+-----+-----------+
# |"sam@tes"...| -1.4| 2020-09...|
# +------------+-----+-----------+
#
# storing them in a temporary view called CustomerRisk
stediEventsStreamingDF.withColumn("value", from_json("value", stediEventJSONSchema)).select(col("value.*")).createOrReplaceTempView("CustomerRisk")

# Execute a sql statement against a temporary view, selecting the customer and the score from the temporary view, creating a dataframe called customerRiskStreamingDF
customerRiskStreamingDF = spark.sql("SELECT customer, score FROM CustomerRisk")
# Sink the customerRiskStreamingDF dataframe to the console in append mode
# 
# It should output like this:
#
# +--------------------+-----
# |customer           |score|
# +--------------------+-----+
# |Spencer.Davis@tes...| 8.0|
# +--------------------+-----
customerRiskStreamingDF.writeStream.outputMode("append").format("console").start().awaitTermination()
# Run the python script by running the command from the terminal:
# /home/workspace/submit-event-kafkastreaming.sh
# Verify the data looks correct 