//+------------------------------------------------------------------+
//|                                              ClonadorOrdenes.mq5 |
//|   Lee TradeEvents.csv (Common\Files) y clona operaciones         |
//|   OPEN/CLOSE/MODIFY del maestro en esta cuenta (MT5)            |
//|   v1.1: añade soporte para eventos MODIFY (cambios SL/TP)       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025"
#property link      "https://www.mql5.com"
#property version   "1.10"
#property description "Clona operaciones desde TradeEvents.csv (Common\\Files)"
#property description "Soporta eventos OPEN, CLOSE y MODIFY"

//--- Inputs
input string InpCsvFileName     = "TradeEvents.csv"; // nombre del CSV en Common\Files
input int    InpTimerSeconds    = 3;                 // cada cuántos segundos revisar
input int    InpSlippagePoints  = 30;                // slippage en puntos para abrir/cerrar
input bool   InpCuentaFondeo    = false;             // true = cuenta de fondeo (copiar lotes)
input double InpFixedLots       = 0.10;              // lote fijo cuando NO es cuenta de fondeo

//--- copia interna del timer
int g_TimerSeconds = 5;

//+------------------------------------------------------------------+
//| HELPERS                                                          |
//+------------------------------------------------------------------+

// Convierte "BUY"/"SELL" a tipo de orden MQL5
ENUM_ORDER_TYPE TextToOrderType(string text)
{
   string t = text;
   StringToUpper(t);

   if(t == "BUY")   return ORDER_TYPE_BUY;
   if(t == "SELL")  return ORDER_TYPE_SELL;

   return WRONG_VALUE;
}

// Convierte "BUY"/"SELL" a tipo de posición MQL5
ENUM_POSITION_TYPE TextToPositionType(string text)
{
   string t = text;
   StringToUpper(t);

   if(t == "BUY")   return POSITION_TYPE_BUY;
   if(t == "SELL")  return POSITION_TYPE_SELL;

   return WRONG_VALUE;
}

// Bid / Ask para un símbolo cualquiera
double GetBid(string symbol)
{
   if(symbol == _Symbol) 
      return SymbolInfoDouble(_Symbol, SYMBOL_BID);
   return SymbolInfoDouble(symbol, SYMBOL_BID);
}

double GetAsk(string symbol)
{
   if(symbol == _Symbol) 
      return SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   return SymbolInfoDouble(symbol, SYMBOL_ASK);
}

// Calcula lotaje esclavo
// - Cuenta de fondeo: copia el lote del maestro
// - No fondeo: usa lote fijo InpFixedLots (normalizado a min/max/step)
double ComputeSlaveLots(string symbol, double masterLots)
{
   if(InpCuentaFondeo)
      return masterLots;

   double rawLots = InpFixedLots;

   double minLot   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double maxLot   = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double lotStep  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(lotStep <= 0.0) lotStep = minLot;

   double lots = rawLots;

   // Redondear al paso de lote hacia abajo
   lots = MathFloor(lots / lotStep) * lotStep;

   // Respetar mínimos y máximos del símbolo
   if(lots < minLot) lots = minLot;
   if(lots > maxLot) lots = maxLot;

   int lotDigits = 2;
   if(lotStep > 0.0)
   {
      double tmp = lotStep;
      lotDigits = 0;
      while(tmp < 1.0 && lotDigits < 4)
      {
         tmp *= 10.0;
         lotDigits++;
      }
   }

   return NormalizeDouble(lots, lotDigits);
}

// Comprueba si YA existe un clon (abierto o en histórico)
// Basado en: símbolo + comentario "CLONE Tkt <ticket>"
bool CloneAlreadyExists(string symbol, string cloneComment)
{
   // 1) POSICIONES ABIERTAS
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(PositionGetString(POSITION_SYMBOL) == symbol &&
         PositionGetString(POSITION_COMMENT) == cloneComment)
         return(true);
   }

   // 2) HISTÓRICO: Simplificado en MQL5
   // Nota: El comentario incluye el ticket del maestro que es único por orden.
   // Si una posición está cerrada, no debería impedir crear un nuevo clon.
   // La verificación del histórico en MQL5 es compleja y requiere iterar sobre deals,
   // por lo que por simplicidad solo verificamos posiciones abiertas.
   // Si necesitas verificación del histórico, se puede implementar iterando sobre
   // HistoryDealsTotal() y usando HistoryDealGetInteger() para obtener POSITION_IDENTIFIER.

   return(false);
}

// Busca el ticket (position identifier) del clon abierto por símbolo y comentario
// Retorna el position identifier si existe, o 0 si no se encuentra
ulong FindClonePositionId(string symbol, string cloneComment)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      if(PositionGetString(POSITION_SYMBOL) == symbol &&
         PositionGetString(POSITION_COMMENT) == cloneComment)
         return(PositionGetInteger(POSITION_IDENTIFIER));
   }
   return(0);
}

// Cierra el clon si está abierto (mismo símbolo + comentario)
bool CloseCloneIfOpen(string symbol, string cloneComment)
{
   ulong positionId = FindClonePositionId(symbol, cloneComment);
   if(positionId == 0)
      return(false); // No encontrado -> ya está cerrado o nunca existió

   if(!PositionSelectByTicket(positionId))
      return(false);

   ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   double lots = PositionGetDouble(POSITION_VOLUME);

   MqlTradeRequest request;
   MqlTradeResult  result;
   ZeroMemory(request);
   ZeroMemory(result);

   request.action    = TRADE_ACTION_DEAL;
   request.position  = positionId;
   request.symbol    = symbol;
   request.volume    = lots;
   request.deviation = InpSlippagePoints;
   request.magic     = 0;
   request.comment   = cloneComment;

   if(type == POSITION_TYPE_BUY)
   {
      request.type = ORDER_TYPE_SELL;
      request.price = GetBid(symbol);
   }
   else
   {
      request.type = ORDER_TYPE_BUY;
      request.price = GetAsk(symbol);
   }

   if(!OrderSend(request, result))
   {
      PrintFormat("OIExecutor(MT5): error al cerrar clon %s (%s). Error=%d: %s",
                  symbol, cloneComment, result.retcode, MyErrorDescription(result.retcode));
      return(false);
   }
   else
   {
      PrintFormat("OIExecutor(MT5): clon CERRADO %s (%s)", symbol, cloneComment);
      return(true);
   }
}

//+------------------------------------------------------------------+
//| Procesa el CSV completo                                          |
//|  - OPEN  -> crear clon (si no existe ni abierto ni en histórico) |
//|  - CLOSE -> cerrar clon si está abierto                          |
//|  - MODIFY -> actualizar SL/TP del clon si está abierto          |
//+------------------------------------------------------------------+
void ProcessCsv()
{
   ResetLastError();

   // Leer en modo BINARIO para evitar problemas de codificación
   int handle = FileOpen(InpCsvFileName, FILE_READ|FILE_BIN|FILE_COMMON|FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(handle == INVALID_HANDLE)
   {
      int err = GetLastError();
      if(err != 4103) // 4103 = archivo no existe
         PrintFormat("OIExecutor(MT5): Error al abrir CSV: %s Error=%d", InpCsvFileName, err);
      return;
   }
   
   // Verificar tamaño del archivo
   ulong file_size = FileSize(handle);
   if(file_size == 0)
   {
      PrintFormat("OIExecutor(MT5): Archivo vacío");
      FileClose(handle);
      return;
   }
   
   // Leer todo el archivo en binario
   uchar bytes[];
   ArrayResize(bytes, (int)file_size);
   uint bytes_read = FileReadArray(handle, bytes, 0, (int)file_size);
   FileClose(handle);
   
   if(bytes_read == 0)
   {
      PrintFormat("OIExecutor(MT5): ERROR - No se pudieron leer bytes del archivo");
      return;
   }
   
   // Detectar y saltar BOM UTF-8 si existe
   int start_pos = 0;
   if(bytes_read >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF)
   {
      start_pos = 3;
   }
   
   // Convertir bytes a string (UTF-8 o ANSI)
   uchar content_bytes[];
   int content_size = bytes_read - start_pos;
   ArrayResize(content_bytes, content_size);
   ArrayCopy(content_bytes, bytes, 0, start_pos, content_size);
   
   string file_content = CharArrayToString(content_bytes, 0, WHOLE_ARRAY, 65001); // UTF-8
   if(StringLen(file_content) == 0)
   {
      file_content = CharArrayToString(content_bytes, 0, WHOLE_ARRAY, 0); // ANSI fallback
   }
   
   if(StringLen(file_content) == 0)
   {
      PrintFormat("OIExecutor(MT5): ERROR - No se pudo convertir contenido a string");
      return;
   }
   
   // Dividir por líneas
   string lines[];
   int line_count = 0;
   
   // Intentar con \r primero (Windows)
   string temp_lines[];
   int temp_count = StringSplit(file_content, '\r', temp_lines);
   if(temp_count > 1)
   {
      ArrayResize(lines, temp_count);
      for(int i = 0; i < temp_count; i++)
      {
         string clean = temp_lines[i];
         StringReplace(clean, "\n", "");
         lines[i] = clean;
      }
      line_count = temp_count;
   }
   else
   {
      line_count = StringSplit(file_content, '\n', lines);
   }
   
   if(line_count < 2)
   {
      PrintFormat("OIExecutor(MT5): Archivo tiene menos de 2 líneas");
      return;
   }
   
   // Procesar cada línea (saltar primera que es la cabecera)
   int processed_count = 0;
   for(int i = 1; i < line_count; i++)
   {
      string line = lines[i];
      
      // Limpiar espacios
      while(StringLen(line) > 0 && StringGetCharacter(line, 0) == ' ')
         line = StringSubstr(line, 1);
      while(StringLen(line) > 0 && StringGetCharacter(line, StringLen(line)-1) == ' ')
         line = StringSubstr(line, 0, StringLen(line)-1);
      
      // Saltar líneas vacías o muy cortas
      if(line == "" || StringLen(line) < 3)
         continue;
      
      // Dividir línea por punto y coma
      string fields[];
      int cnt = StringSplit(line, ';', fields);
      
      if(cnt < 5)
      {
         PrintFormat("OIExecutor(MT5): Línea tiene solo %d campos (mínimo 5 requeridos), saltando: '%s'", cnt, line);
         continue;
      }
      
      // Extraer campos principales
      string event_type      = fields[0];
      string masterTicketStr = fields[1];
      string orderTypeText   = fields[2];
      string lotsText        = fields[3];
      string symbol          = fields[4];
      
      // Comentario estándar del clon
      string cloneComment = "CLONE Tkt " + masterTicketStr;

      //========================
      // 1) OPEN  -> crear clon
      //========================
      if(event_type == "OPEN")
      {
         double masterLots = StringToDouble(lotsText);
         double lots       = ComputeSlaveLots(symbol, masterLots);

         // sl y tp en campos 7 y 8 (si existen)
         double sl = 0.0;
         double tp = 0.0;
         if(cnt > 7 && fields[7] != "")
            sl = StringToDouble(fields[7]);
         if(cnt > 8 && fields[8] != "")
            tp = StringToDouble(fields[8]);

         // Evitar duplicados (abiertos o ya cerrados en el pasado)
         if(CloneAlreadyExists(symbol, cloneComment))
            continue;

         ENUM_ORDER_TYPE orderType = TextToOrderType(orderTypeText);
         if(orderType != ORDER_TYPE_BUY && orderType != ORDER_TYPE_SELL)
         {
            PrintFormat("OIExecutor(MT5): tipo de orden no soportado '%s' en línea '%s'",
                        orderTypeText, line);
            continue;
         }

         double price = (orderType == ORDER_TYPE_BUY ? GetAsk(symbol) : GetBid(symbol));

         MqlTradeRequest request;
         MqlTradeResult  result;
         ZeroMemory(request);
         ZeroMemory(result);

         request.action    = TRADE_ACTION_DEAL;
         request.symbol    = symbol;
         request.volume    = lots;
         request.type      = orderType;
         request.price     = price;
         request.deviation = InpSlippagePoints;
         request.sl        = sl;
         request.tp        = tp;
         request.magic     = 0;
         request.comment   = cloneComment;

         if(!OrderSend(request, result))
         {
            PrintFormat("OrderSend fallo. Maestro %s, símbolo %s, lots=%.2f. Error %d: %s",
               masterTicketStr,
               symbol,
               lots,
               result.retcode,
               MyErrorDescription(result.retcode));        
         }
         else
         {
            PrintFormat("OIExecutor(MT5): CLONE creado %s %s lots=%.2f SL=%.5f TP=%.5f (maestro %s)",
                        symbol, orderTypeText, lots, sl, tp, masterTicketStr);
         }
      }
      //========================
      // 2) CLOSE -> cerrar clon
      //========================
      else if(event_type == "CLOSE")
      {
         CloseCloneIfOpen(symbol, cloneComment);
      }
      //========================
      // 3) MODIFY -> actualizar SL/TP del clon
      //========================
      else if(event_type == "MODIFY")
      {
         ulong positionId = FindClonePositionId(symbol, cloneComment);
         if(positionId == 0)
         {
            // Clon no encontrado (ya cerrado o nunca existió) - ignorar silenciosamente
            continue;
         }

         if(!PositionSelectByTicket(positionId))
         {
            PrintFormat("OIExecutor(MT5): no se pudo seleccionar clon %llu para modificar", positionId);
            continue;
         }

         // Leer nuevos SL/TP del CSV (campos 7 y 8)
         double newSL = 0.0;
         double newTP = 0.0;
         if(cnt > 7 && fields[7] != "")
            newSL = StringToDouble(fields[7]);
         if(cnt > 8 && fields[8] != "")
            newTP = StringToDouble(fields[8]);

         // Modificar el clon con los nuevos SL/TP
         MqlTradeRequest request;
         MqlTradeResult  result;
         ZeroMemory(request);
         ZeroMemory(result);

         request.action   = TRADE_ACTION_SLTP;
         request.position = positionId;
         request.symbol   = symbol;
         request.sl       = newSL;
         request.tp       = newTP;
         request.magic    = 0;

         if(!OrderSend(request, result))
         {
            PrintFormat("OIExecutor(MT5): error al modificar clon %s (%s) SL=%.5f TP=%.5f. Error %d: %s",
                        symbol, cloneComment, newSL, newTP, result.retcode, MyErrorDescription(result.retcode));
         }
         else
         {
            PrintFormat("OIExecutor(MT5): clon MODIFICADO %s (%s) SL=%.5f TP=%.5f (maestro %s)",
                        symbol, cloneComment, newSL, newTP, masterTicketStr);
         }
      }
      // Otros tipos se ignoran
      
      processed_count++;
   }
   
   PrintFormat("OIExecutor(MT5): Procesamiento completado. %d líneas procesadas", processed_count);
}

//+------------------------------------------------------------------+
//| Eventos                                                          |
//+------------------------------------------------------------------+
int OnInit()
{
   g_TimerSeconds = InpTimerSeconds;
   if(g_TimerSeconds < 1)
      g_TimerSeconds = 1;

   EventSetTimer(g_TimerSeconds);
   PrintFormat("OIExecutor(MT5): iniciado. Leyendo '%s' cada %d s",
               InpCsvFileName, g_TimerSeconds);
   return(INIT_SUCCEEDED);
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
}
//+------------------------------------------------------------------+
void OnTick()
{
   // Todo el trabajo va por OnTimer.
}
//+------------------------------------------------------------------+
void OnTimer()
{
   ProcessCsv();
}
//+------------------------------------------------------------------+

string MyErrorDescription(int code)
{
   switch(code)
   {
      // ---- Genéricos / conexión / cuenta ----
      case 10004: return "TRADE_RETCODE_REQUOTE: Requote";
      case 10006: return "TRADE_RETCODE_REJECT: Request rejected";
      case 10007: return "TRADE_RETCODE_CANCEL: Request canceled";
      case 10008: return "TRADE_RETCODE_PLACED: Order placed";
      case 10009: return "TRADE_RETCODE_DONE: Request executed";
      case 10010: return "TRADE_RETCODE_DONE_PARTIAL: Request partially executed";
      case 10011: return "TRADE_RETCODE_ERROR: Common error";
      case 10012: return "TRADE_RETCODE_TIMEOUT: Timeout";
      case 10013: return "TRADE_RETCODE_INVALID: Invalid request";
      case 10014: return "TRADE_RETCODE_INVALID_VOLUME: Invalid volume";
      case 10015: return "TRADE_RETCODE_INVALID_PRICE: Invalid price";
      case 10016: return "TRADE_RETCODE_INVALID_STOPS: Invalid stops";
      case 10017: return "TRADE_RETCODE_TRADE_DISABLED: Trade disabled";
      case 10018: return "TRADE_RETCODE_MARKET_CLOSED: Market closed";
      case 10019: return "TRADE_RETCODE_NO_MONEY: Not enough money";
      case 10020: return "TRADE_RETCODE_PRICE_CHANGED: Price changed";
      case 10021: return "TRADE_RETCODE_PRICE_OFF: Off quotes";
      case 10022: return "TRADE_RETCODE_INVALID_EXPIRATION: Invalid expiration";
      case 10023: return "TRADE_RETCODE_ORDER_CHANGED: Order changed";
      case 10024: return "TRADE_RETCODE_TOO_MANY_REQUESTS: Too many requests";
      case 10025: return "TRADE_RETCODE_NO_CHANGES: No changes";
      case 10026: return "TRADE_RETCODE_SERVER_DISABLES_AT: Server disables auto trading";
      case 10027: return "TRADE_RETCODE_CLIENT_DISABLES_AT: Client disables auto trading";
      case 10028: return "TRADE_RETCODE_LOCKED: Locked";
      case 10029: return "TRADE_RETCODE_FROZEN: Frozen";
      case 10030: return "TRADE_RETCODE_INVALID_FILL: Invalid fill";
      case 10031: return "TRADE_RETCODE_CONNECTION: No connection";
      case 10032: return "TRADE_RETCODE_ONLY_REAL: Only real accounts allowed";
      case 10033: return "TRADE_RETCODE_LIMIT_ORDERS: Limit orders reached";
      case 10034: return "TRADE_RETCODE_LIMIT_VOLUME: Limit volume reached";
      case 10035: return "TRADE_RETCODE_INVALID_ORDER: Invalid order";
      case 10036: return "TRADE_RETCODE_POSITION_CLOSED: Position closed";

      // ---- Errores del sistema ----
      case 4000: return "4000: Error interno del terminal (no error detail)";
      case 4001: return "4001: Puntero de función incorrecto";
      case 4002: return "4002: Índice de array fuera de rango";
      case 4003: return "4003: Sin memoria para la pila de llamadas (call stack)";
      case 4004: return "4004: Desbordamiento de recursión (recursion stack overflow)";
      case 4005: return "4005: Pila de ejecución insuficiente (not enough stack for parameter)";
      case 4006: return "4006: Sin memoria para cadena (string)";
      case 4007: return "4007: Sin memoria para array";
      case 4008: return "4008: Sin memoria para historial";
      case 4009: return "4009: Sin memoria para indicador personalizado";

      // ---- Errores muy típicos al programar EAs ----
      case 4106: return "4106: Símbolo desconocido o no válido";
      case 4107: return "4107: Parámetro de precio no válido";
      case 4108: return "4108: Ticket de orden no válido";
      case 4109: return "4109: Trade not allowed (AutoTrading desactivado o EA sin permisos)";
      case 4110: return "4110: Solo posiciones largas permitidas para este símbolo";

      default:
         return "Error " + IntegerToString(code) + ": descripción no definida en MyErrorDescription()";
   }
}


