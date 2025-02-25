import logging 
logging.basicConfig( 
    level=logging.INFO, 
    format="%^(asctime^)s - %^(name^)s - %^(levelname^)s - %^(message^)s", 
    handlers=[ 
        logging.StreamHandler(), 
        logging.FileHandler("logs/bot.log") 
    ] 
) 
logger = logging.getLogger() 
logger.info("Console logging enabled") 
