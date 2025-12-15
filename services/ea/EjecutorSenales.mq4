//+------------------------------------------------------------------+
//|                                          EjecutorSenales.mq4     |
//|   Lee colaMT4.csv (Common\Files) y ejecuta acciones de trading  |
//|   BUY, SELL, SL A, VARIOS SL A, BREAKEVEN, PARCIAL, CERRAR       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025"
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict
#property description "Lee colaMT4.csv y ejecuta acciones de trading cada 2 segundos"

//--- Inputs
input double InpVolume      = 0.01;  // Volumen en lotes para BUY/SELL
input int    InpSlippage    = 30;    // Slippage en puntos
input int    InpMagicNumber = 0;     // Magic Number (0 = sin magic)

//--- Constantes
#define CSV_FILENAME "colaMT4.csv"
#define CONTROL_FILENAME "colaMT4_control.txt"
#define TIMER_SECONDS 2

//--- Arrays para gestión de reintentos
string g_oids_fallidos[];           // oids con contador >= 3
string g_oids_reintentando[];       // oids con contador 0, 1, 2
int    g_contadores_reintentos[];   // contador paralelo a g_oids_reintentando[]

//--- Mapeo de channels a códigos numéricos
string g_channels[] = {"JB UNITED", "JB TORO", "JB GOLD VIP IÑAKI", "PRUEBAS RUBEN Y JACINTO"};
int    g_codigos[]  = {1, 2, 3, 4};

//+------------------------------------------------------------------+
//| Función auxiliar: Obtener código numérico del channel            |
//+------------------------------------------------------------------+
int GetChannelCode(string channel)
{
   for(int i = 0; i < ArraySize(g_channels); i++)
   {
      if(g_channels[i] == channel)
         return g_codigos[i];
   }
   return 0; // Si no coincide, devolver 0
}

//+------------------------------------------------------------------+
//| Función auxiliar: Construir comment (oid + código)              |
//+------------------------------------------------------------------+
string BuildComment(string oid, int codigo)
{
   return oid + "-" + IntegerToString(codigo);
}

//+------------------------------------------------------------------+
//| Función auxiliar: Verificar si oid está en array                |
//+------------------------------------------------------------------+
bool IsOidInArray(string oid, string &array[])
{
   for(int i = 0; i < ArraySize(array); i++)
   {
      if(array[i] == oid)
         return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Obtener índice de oid en array                |
//+------------------------------------------------------------------+
int GetOidIndex(string oid, string &array[])
{
   for(int i = 0; i < ArraySize(array); i++)
   {
      if(array[i] == oid)
         return i;
   }
   return -1;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Añadir oid a array                            |
//+------------------------------------------------------------------+
void AddOidToArray(string oid, string &array[])
{
   int size = ArraySize(array);
   ArrayResize(array, size + 1);
   array[size] = oid;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Eliminar oid de array                         |
//+------------------------------------------------------------------+
void RemoveOidFromArray(string oid, string &array[])
{
   int idx = GetOidIndex(oid, array);
   if(idx < 0) return;
   
   int size = ArraySize(array);
   for(int i = idx; i < size - 1; i++)
      array[i] = array[i + 1];
   ArrayResize(array, size - 1);
}

//+------------------------------------------------------------------+
//| Función auxiliar: Obtener contador de reintentos                |
//+------------------------------------------------------------------+
int GetRetryCount(string oid)
{
   int idx = GetOidIndex(oid, g_oids_reintentando);
   if(idx < 0) return 0;
   
   if(idx < ArraySize(g_contadores_reintentos))
      return g_contadores_reintentos[idx];
   return 0;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Establecer contador de reintentos             |
//+------------------------------------------------------------------+
void SetRetryCount(string oid, int count)
{
   int idx = GetOidIndex(oid, g_oids_reintentando);
   if(idx < 0)
   {
      // Añadir nuevo oid
      AddOidToArray(oid, g_oids_reintentando);
      idx = ArraySize(g_oids_reintentando) - 1;
      ArrayResize(g_contadores_reintentos, idx + 1);
   }
   
   if(idx < ArraySize(g_contadores_reintentos))
      g_contadores_reintentos[idx] = count;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Verificar si orden existe en historial        |
//+------------------------------------------------------------------+
bool OrderExistsInHistory(string comment)
{
   // Buscar en posiciones abiertas
   for(int i = 0; i < OrdersTotal(); i++)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         if(StringFind(OrderComment(), comment) >= 0)
            return true;
      }
   }
   
   // Buscar en historial
   for(int i = 0; i < OrdersHistoryTotal(); i++)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_HISTORY))
      {
         if(StringFind(OrderComment(), comment) >= 0)
            return true;
      }
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Buscar posiciones por comment                 |
//+------------------------------------------------------------------+
int FindPositionsByComment(string comment, string symbol_filter, int &tickets[])
{
   ArrayResize(tickets, 0);
   int count = 0;
   
   for(int i = 0; i < OrdersTotal(); i++)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         // Verificar comment
         if(StringFind(OrderComment(), comment) < 0)
            continue;
         
         // Verificar symbol si viene filtro
         if(symbol_filter != "" && OrderSymbol() != symbol_filter)
            continue;
         
         // Añadir ticket
         ArrayResize(tickets, count + 1);
         tickets[count] = OrderTicket();
         count++;
      }
   }
   
   return count;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Leer archivo de control                       |
//+------------------------------------------------------------------+
void LoadControlFile()
{
   int handle = FileOpen(CONTROL_FILENAME, FILE_READ|FILE_TXT|FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      // Archivo no existe, inicializar arrays vacíos
      ArrayResize(g_oids_fallidos, 0);
      ArrayResize(g_oids_reintentando, 0);
      ArrayResize(g_contadores_reintentos, 0);
      return;
   }
   
   ArrayResize(g_oids_fallidos, 0);
   ArrayResize(g_oids_reintentando, 0);
   ArrayResize(g_contadores_reintentos, 0);
   
   while(!FileIsEnding(handle))
   {
      string line = FileReadString(handle);
      if(line == "" || StringLen(line) < 3)
         continue;
      
      int sep_pos = StringFind(line, "|");
      if(sep_pos < 0)
         continue;
      
      string oid = StringSubstr(line, 0, sep_pos);
      string count_str = StringSubstr(line, sep_pos + 1);
      int count = (int)StringToInteger(count_str);
      
      if(count >= 3)
      {
         AddOidToArray(oid, g_oids_fallidos);
      }
      else
      {
         AddOidToArray(oid, g_oids_reintentando);
         int idx = ArraySize(g_oids_reintentando) - 1;
         ArrayResize(g_contadores_reintentos, idx + 1);
         g_contadores_reintentos[idx] = count;
      }
   }
   
   FileClose(handle);
}

//+------------------------------------------------------------------+
//| Función auxiliar: Escribir archivo de control                   |
//+------------------------------------------------------------------+
void SaveControlFile()
{
   int handle = FileOpen(CONTROL_FILENAME, FILE_WRITE|FILE_TXT|FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      Print("Error: No se pudo crear archivo de control");
      return;
   }
   
   // Escribir oids en reintento
   for(int i = 0; i < ArraySize(g_oids_reintentando); i++)
   {
      int count = 0;
      if(i < ArraySize(g_contadores_reintentos))
         count = g_contadores_reintentos[i];
      
      string line = g_oids_reintentando[i] + "|" + IntegerToString(count);
      FileWrite(handle, line);
   }
   
   // Escribir oids fallidos (contador >= 3)
   for(int i = 0; i < ArraySize(g_oids_fallidos); i++)
   {
      string line = g_oids_fallidos[i] + "|3";
      FileWrite(handle, line);
   }
   
   FileClose(handle);
}

//+------------------------------------------------------------------+
//| Función auxiliar: Actualizar oid en archivo de control          |
//+------------------------------------------------------------------+
void UpdateControlFile(string oid, int count)
{
   // Actualizar en memoria
   if(count >= 3)
   {
      // Mover a fallidos
      RemoveOidFromArray(oid, g_oids_reintentando);
      int idx = GetOidIndex(oid, g_oids_reintentando);
      if(idx >= 0 && idx < ArraySize(g_contadores_reintentos))
      {
         // Eliminar contador
         for(int i = idx; i < ArraySize(g_contadores_reintentos) - 1; i++)
            g_contadores_reintentos[i] = g_contadores_reintentos[i + 1];
         ArrayResize(g_contadores_reintentos, ArraySize(g_contadores_reintentos) - 1);
      }
      
      if(!IsOidInArray(oid, g_oids_fallidos))
         AddOidToArray(oid, g_oids_fallidos);
   }
   else
   {
      SetRetryCount(oid, count);
   }
   
   // Guardar archivo
   SaveControlFile();
}

//+------------------------------------------------------------------+
//| Función auxiliar: Eliminar oid del archivo de control          |
//+------------------------------------------------------------------+
void RemoveFromControlFile(string oid)
{
   RemoveOidFromArray(oid, g_oids_reintentando);
   int idx = GetOidIndex(oid, g_oids_reintentando);
   if(idx >= 0 && idx < ArraySize(g_contadores_reintentos))
   {
      // Eliminar contador
      for(int i = idx; i < ArraySize(g_contadores_reintentos) - 1; i++)
         g_contadores_reintentos[i] = g_contadores_reintentos[i + 1];
      ArrayResize(g_contadores_reintentos, ArraySize(g_contadores_reintentos) - 1);
   }
   
   SaveControlFile();
}

//+------------------------------------------------------------------+
//| Función auxiliar: Verificar limpieza automática                |
//+------------------------------------------------------------------+
void CheckAutoCleanup()
{
   int handle = FileOpen(CONTROL_FILENAME, FILE_READ|FILE_TXT|FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return; // Archivo no existe, nada que limpiar
   
   datetime file_time = (datetime)FileGetInteger(handle, FILE_MODIFY_DATE);
   FileClose(handle);
   
   datetime current_time = TimeCurrent();
   MqlDateTime dt_file, dt_current;
   TimeToStruct(file_time, dt_file);
   TimeToStruct(current_time, dt_current);
   
   // Comparar fechas (solo día, mes, año)
   if(dt_file.year < dt_current.year ||
      (dt_file.year == dt_current.year && dt_file.mon < dt_current.mon) ||
      (dt_file.year == dt_current.year && dt_file.mon == dt_current.mon && dt_file.day < dt_current.day))
   {
      // Es un día diferente, eliminar archivo
      FileDelete(CONTROL_FILENAME, FILE_COMMON);
      Print("Archivo de control eliminado (nuevo día)");
   }
}

//+------------------------------------------------------------------+
//| Función auxiliar: Trim de string                                |
//+------------------------------------------------------------------+
string TrimString(string str)
{
   int len = StringLen(str);
   int start = 0;
   int end = len - 1;
   
   // Encontrar inicio sin espacios
   while(start < len && StringGetCharacter(str, start) == ' ')
      start++;
   
   // Encontrar fin sin espacios
   while(end >= start && StringGetCharacter(str, end) == ' ')
      end--;
   
   if(start > end)
      return "";
   
   return StringSubstr(str, start, end - start + 1);
}

//+------------------------------------------------------------------+
//| Función auxiliar: Parsear línea CSV                             |
//+------------------------------------------------------------------+
bool ParseCsvLine(string line, string &fields[])
{
   ArrayResize(fields, 0);
   int count = 0;
   int start = 0;
   int len = StringLen(line);
   
   for(int i = 0; i <= len; i++)
   {
      bool is_comma = (i < len && StringGetCharacter(line, i) == ',');
      bool is_end = (i == len);
      
      if(is_comma || is_end)
      {
         string field = "";
         if(i > start)
            field = StringSubstr(line, start, i - start);
         
         ArrayResize(fields, count + 1);
         fields[count] = field;
         count++;
         start = i + 1;
      }
   }
   
   return (count >= 13); // Mínimo 13 campos esperados
}

//+------------------------------------------------------------------+
//| Función auxiliar: Ejecutar acción BUY                           |
//+------------------------------------------------------------------+
bool ExecuteBUY(string symbol, double sl, double tp1, string comment)
{
   double price = MarketInfo(symbol, MODE_ASK);
   int ticket = OrderSend(symbol, OP_BUY, InpVolume, price, InpSlippage, sl, tp1, comment, InpMagicNumber, 0, clrGreen);
   
   if(ticket > 0)
   {
      Print("BUY ejecutado: ", symbol, " Ticket=", ticket, " Comment=", comment);
      return true;
   }
   else
   {
      Print("Error BUY: ", symbol, " Error=", GetLastError(), " Comment=", comment);
      return false;
   }
}

//+------------------------------------------------------------------+
//| Función auxiliar: Ejecutar acción SELL                          |
//+------------------------------------------------------------------+
bool ExecuteSELL(string symbol, double sl, double tp1, string comment)
{
   double price = MarketInfo(symbol, MODE_BID);
   int ticket = OrderSend(symbol, OP_SELL, InpVolume, price, InpSlippage, sl, tp1, comment, InpMagicNumber, 0, clrRed);
   
   if(ticket > 0)
   {
      Print("SELL ejecutado: ", symbol, " Ticket=", ticket, " Comment=", comment);
      return true;
   }
   else
   {
      Print("Error SELL: ", symbol, " Error=", GetLastError(), " Comment=", comment);
      return false;
   }
}

//+------------------------------------------------------------------+
//| Función auxiliar: Ejecutar acción SL A                         |
//+------------------------------------------------------------------+
bool ExecuteSLA(string comment, string symbol_filter, double new_sl)
{
   int tickets[];
   int count = FindPositionsByComment(comment, symbol_filter, tickets);
   
   if(count == 0)
   {
      Print("SL A: No se encontraron posiciones con comment=", comment);
      return false;
   }
   
   if(count > 1)
   {
      Print("SL A: Se encontraron múltiples posiciones, usando la primera");
   }
   
   if(OrderSelect(tickets[0], SELECT_BY_TICKET, MODE_TRADES))
   {
      double open_price = OrderOpenPrice();
      double tp = OrderTakeProfit();
      
      bool result = OrderModify(tickets[0], open_price, new_sl, tp, 0, clrBlue);
      if(result)
      {
         Print("SL A ejecutado: Ticket=", tickets[0], " Nuevo SL=", new_sl);
         return true;
      }
      else
      {
         Print("Error SL A: Ticket=", tickets[0], " Error=", GetLastError());
         return false;
      }
   }
   
   return false;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Ejecutar acción VARIOS SL A                   |
//+------------------------------------------------------------------+
bool ExecuteVariosSLA(string comment, string symbol_filter, double new_sl)
{
   int tickets[];
   int count = FindPositionsByComment(comment, symbol_filter, tickets);
   
   if(count == 0)
   {
      Print("VARIOS SL A: No se encontraron posiciones con comment=", comment);
      return false;
   }
   
   bool all_success = true;
   for(int i = 0; i < count; i++)
   {
      if(OrderSelect(tickets[i], SELECT_BY_TICKET, MODE_TRADES))
      {
         double open_price = OrderOpenPrice();
         double tp = OrderTakeProfit();
         
         bool result = OrderModify(tickets[i], open_price, new_sl, tp, 0, clrBlue);
         if(result)
         {
            Print("VARIOS SL A ejecutado: Ticket=", tickets[i], " Nuevo SL=", new_sl);
         }
         else
         {
            Print("Error VARIOS SL A: Ticket=", tickets[i], " Error=", GetLastError());
            all_success = false;
         }
      }
   }
   
   return all_success;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Ejecutar acción BREAKEVEN                    |
//+------------------------------------------------------------------+
bool ExecuteBREAKEVEN(string comment, string symbol_filter)
{
   int tickets[];
   int count = FindPositionsByComment(comment, symbol_filter, tickets);
   
   if(count == 0)
   {
      Print("BREAKEVEN: No se encontraron posiciones con comment=", comment);
      return false;
   }
   
   bool all_success = true;
   for(int i = 0; i < count; i++)
   {
      if(OrderSelect(tickets[i], SELECT_BY_TICKET, MODE_TRADES))
      {
         double open_price = OrderOpenPrice();
         double tp = OrderTakeProfit();
         
         bool result = OrderModify(tickets[i], open_price, open_price, tp, 0, clrBlue);
         if(result)
         {
            Print("BREAKEVEN ejecutado: Ticket=", tickets[i], " SL=", open_price);
         }
         else
         {
            Print("Error BREAKEVEN: Ticket=", tickets[i], " Error=", GetLastError());
            all_success = false;
         }
      }
   }
   
   return all_success;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Ejecutar acción PARCIAL                       |
//+------------------------------------------------------------------+
bool ExecutePARCIAL(string comment, string symbol_filter)
{
   int tickets[];
   int count = FindPositionsByComment(comment, symbol_filter, tickets);
   
   if(count == 0)
   {
      Print("PARCIAL: No se encontraron posiciones con comment=", comment);
      return false;
   }
   
   bool all_success = true;
   for(int i = 0; i < count; i++)
   {
      if(OrderSelect(tickets[i], SELECT_BY_TICKET, MODE_TRADES))
      {
         double lots = OrderLots();
         double partial_lots = lots / 2.0;
         double price;
         
         if(OrderType() == OP_BUY)
            price = MarketInfo(OrderSymbol(), MODE_BID);
         else
            price = MarketInfo(OrderSymbol(), MODE_ASK);
         
         bool result = OrderClose(tickets[i], partial_lots, price, InpSlippage, clrOrange);
         if(result)
         {
            Print("PARCIAL ejecutado: Ticket=", tickets[i], " Lots=", partial_lots);
         }
         else
         {
            Print("Error PARCIAL: Ticket=", tickets[i], " Error=", GetLastError());
            all_success = false;
         }
      }
   }
   
   return all_success;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Ejecutar acción CERRAR                        |
//+------------------------------------------------------------------+
bool ExecuteCERRAR(string comment, string symbol_filter)
{
   int tickets[];
   int count = FindPositionsByComment(comment, symbol_filter, tickets);
   
   if(count == 0)
   {
      Print("CERRAR: No se encontraron posiciones con comment=", comment);
      return false;
   }
   
   bool all_success = true;
   for(int i = 0; i < count; i++)
   {
      if(OrderSelect(tickets[i], SELECT_BY_TICKET, MODE_TRADES))
      {
         double lots = OrderLots();
         double price;
         
         if(OrderType() == OP_BUY)
            price = MarketInfo(OrderSymbol(), MODE_BID);
         else
            price = MarketInfo(OrderSymbol(), MODE_ASK);
         
         bool result = OrderClose(tickets[i], lots, price, InpSlippage, clrRed);
         if(result)
         {
            Print("CERRAR ejecutado: Ticket=", tickets[i]);
         }
         else
         {
            Print("Error CERRAR: Ticket=", tickets[i], " Error=", GetLastError());
            all_success = false;
         }
      }
   }
   
   return all_success;
}

//+------------------------------------------------------------------+
//| Función auxiliar: Procesar registro del CSV                     |
//+------------------------------------------------------------------+
void ProcessCsvRecord(string &fields[])
{
   if(ArraySize(fields) < 13)
      return;
   
   string oid = TrimString(fields[0]);
   string symbol = TrimString(fields[2]);
   string order_type = TrimString(fields[3]);
   string entry_price_str = TrimString(fields[4]);
   string sl_str = TrimString(fields[5]);
   string tp1_str = TrimString(fields[6]);
   string channel = TrimString(fields[12]);
   
   // Verificar si oid está en fallidos
   if(IsOidInArray(oid, g_oids_fallidos))
   {
      Print("OID ignorado (ya falló 3 veces): ", oid);
      return;
   }
   
   // Obtener contador de reintentos
   int retry_count = GetRetryCount(oid);
   
   // Convertir channel a código
   int codigo = GetChannelCode(channel);
   if(codigo == 0)
   {
      Print("Channel no reconocido: ", channel, " OID: ", oid);
      return;
   }
   
   // Construir comment
   string comment = BuildComment(oid, codigo);
   
   // Verificar si orden ya existe en historial
   if(OrderExistsInHistory(comment))
   {
      Print("Orden ya existe en historial, ignorando: ", oid, " Comment: ", comment);
      RemoveFromControlFile(oid); // Limpiar de control si estaba
      return;
   }
   
   // Ejecutar acción según order_type
   bool success = false;
   
   if(order_type == "BUY")
   {
      if(symbol == "")
      {
         Print("BUY: Symbol vacío, ignorando OID: ", oid);
         return;
      }
      double sl = StringToDouble(sl_str);
      double tp1 = StringToDouble(tp1_str);
      success = ExecuteBUY(symbol, sl, tp1, comment);
   }
   else if(order_type == "SELL")
   {
      if(symbol == "")
      {
         Print("SELL: Symbol vacío, ignorando OID: ", oid);
         return;
      }
      double sl = StringToDouble(sl_str);
      double tp1 = StringToDouble(tp1_str);
      success = ExecuteSELL(symbol, sl, tp1, comment);
   }
   else if(order_type == "SL A")
   {
      double new_sl = StringToDouble(sl_str);
      success = ExecuteSLA(comment, symbol, new_sl);
   }
   else if(order_type == "VARIOS SL A")
   {
      double new_sl = StringToDouble(sl_str);
      success = ExecuteVariosSLA(comment, symbol, new_sl);
   }
   else if(order_type == "BREAKEVEN")
   {
      success = ExecuteBREAKEVEN(comment, symbol);
   }
   else if(order_type == "PARCIAL")
   {
      success = ExecutePARCIAL(comment, symbol);
   }
   else if(order_type == "CERRAR")
   {
      success = ExecuteCERRAR(comment, symbol);
   }
   else
   {
      Print("Tipo de orden no reconocido: ", order_type, " OID: ", oid);
      return;
   }
   
   // Gestionar resultado
   if(success)
   {
      // Éxito: eliminar de control
      RemoveFromControlFile(oid);
      Print("Acción exitosa: ", order_type, " OID: ", oid);
   }
   else
   {
      // Falla: incrementar contador
      retry_count++;
      UpdateControlFile(oid, retry_count);
      
      if(retry_count >= 3)
      {
         Print("OID marcado como fallido (3 intentos): ", oid);
      }
      else
      {
         Print("Reintento ", retry_count, "/3 para OID: ", oid);
      }
   }
}

//+------------------------------------------------------------------+
//| Función principal: Procesar CSV                                 |
//+------------------------------------------------------------------+
void ProcessCsv()
{
   int handle = FileOpen(CSV_FILENAME, FILE_READ|FILE_TXT|FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      int err = GetLastError();
      if(err != 4103) // 4103 = archivo no existe
         Print("Error al abrir CSV: ", CSV_FILENAME, " Error=", err);
      return;
   }
   
   // Saltar cabecera (primera línea)
   if(!FileIsEnding(handle))
      FileReadString(handle);
   
   // Procesar cada línea
   while(!FileIsEnding(handle))
   {
      string line = FileReadString(handle);
      if(line == "" || StringLen(line) < 3)
         continue;
      
      string fields[];
      if(ParseCsvLine(line, fields))
      {
         ProcessCsvRecord(fields);
      }
   }
   
   FileClose(handle);
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Verificar limpieza automática
   CheckAutoCleanup();
   
   // Cargar archivo de control
   LoadControlFile();
   
   // Configurar timer
   EventSetTimer(TIMER_SECONDS);
   
   Print("EjecutorSenales iniciado. Leyendo ", CSV_FILENAME, " cada ", TIMER_SECONDS, " segundos");
   Print("Volume=", InpVolume, " Slippage=", InpSlippage, " Magic=", InpMagicNumber);
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("EjecutorSenales detenido");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Todo el trabajo se hace en OnTimer
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   ProcessCsv();
}

//+------------------------------------------------------------------+

