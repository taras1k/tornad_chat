import tornadoredis

c = tornadoredis.Client(selected_db='massages')
c.connect()
