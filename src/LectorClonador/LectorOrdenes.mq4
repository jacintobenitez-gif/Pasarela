//+------------------------------------------------------------------+
//|                                                LectorOrdenes.mq4 |
//|                                  Copyright 2025, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//|   Lee aperturas y cierres y los escribe en Common\Files          |
//|   Fichero: TradeEvents.csv (compartido por todos los MT4/MT5)    |
//|   v1.1: añade columnas SL y TP                                   |
//+------------------------------------------------------------------+
#property strict

// Nombre del fichero CSV (en carpeta COMMON\Files)
input string InpCSVFileName = "TradeEvents.csv";

// Tamaño máximo de órdenes que vamos a manejar
#define MAX_ORDERS 500

int  g_prevTickets[MAX_ORDERS];  // Tickets abiertos en el tick anterior
int  g_prevCount      = 0;       // Cuántos había
bool g_initialized    = false;   // Para no disparar eventos en el primer tick

//+------------------------------------------------------------------+
//| Devuelve true si el ticket está en el array (size elementos)     |
//+------------------------------------------------------------------+
bool TicketInArray(int ticket, int &arr[], int size)
{
   for(int i = 0; i < size; i++)
   {
      if(arr[i] == ticket)
         return(true);
   }
   return(false);
}

//+------------------------------------------------------------------+
//| Escribe una línea en el CSV (apertura o cierre)                  |
//| v1.1: añade sl y tp                                              |
//+------------------------------------------------------------------+
void AppendEventToCSV(string eventType,
                      int    ticket,
                      string orderTypeStr,
                      double lots,
                      string symbol,
                      double openPrice,
                      datetime openTime,
                      double sl,
                      double tp,
                      double closePrice,
                      datetime closeTime,
                      double profit,
                      int    magic,
                      string comment)
{
   // *** IMPORTANTE: READ + WRITE para NO truncar el fichero ***
   int handle = FileOpen(InpCSVFileName,
                         FILE_CSV | FILE_READ | FILE_WRITE | FILE_COMMON |
                         FILE_SHARE_READ | FILE_SHARE_WRITE,
                         ';');

   if(handle == INVALID_HANDLE)
   {
      Print("Observador_Common: ERROR al abrir CSV '", InpCSVFileName,
            "' err=", GetLastError());
      return;
   }

   // Ir al final para añadir
   FileSeek(handle, 0, SEEK_END);

   string sLots       = DoubleToString(lots, 2);
   string sOpenPrice  = (openPrice  > 0.0 ? DoubleToString(openPrice,  Digits) : "");
   string sClosePrice = (closePrice > 0.0 ? DoubleToString(closePrice, Digits) : "");
   string sSL         = (sl > 0.0 ? DoubleToString(sl, Digits) : "");
   string sTP         = (tp > 0.0 ? DoubleToString(tp, Digits) : "");

   string sOpenTime   = (openTime  > 0 ? TimeToStr(openTime,  TIME_DATE|TIME_SECONDS)  : "");
   string sCloseTime  = (closeTime > 0 ? TimeToStr(closeTime, TIME_DATE|TIME_SECONDS)  : "");

   string sProfit     = DoubleToString(profit, 2);

   FileWrite(handle,
             eventType,      // 1  OPEN / CLOSE
             ticket,         // 2
             orderTypeStr,   // 3
             sLots,          // 4
             symbol,         // 5
             sOpenPrice,     // 6
             sOpenTime,      // 7
             sSL,            // 8
             sTP,            // 9
             sClosePrice,    // 10
             sCloseTime,     // 11
             sProfit,        // 12
             magic,          // 13
             comment);       // 14

   FileClose(handle);
}

//+------------------------------------------------------------------+
//| Inicializa el CSV (cabecera) en COMMON\Files si no existe        |
//| v1.1: cabecera con sl y tp                                      |
//+------------------------------------------------------------------+
void InitCSVIfNeeded()
{
   // Intentar abrir en lectura en carpeta COMMON
   int hRead = FileOpen(InpCSVFileName,
                        FILE_CSV | FILE_READ |
                        FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE,
                        ';');
   if(hRead != INVALID_HANDLE)
   {
      FileClose(hRead);
      return; // ya existe
   }

   // No existe: crear y escribir cabecera nueva
   int handle = FileOpen(InpCSVFileName,
                         FILE_CSV | FILE_WRITE |
                         FILE_COMMON | FILE_SHARE_READ | FILE_SHARE_WRITE,
                         ';');
   if(handle == INVALID_HANDLE)
   {
      Print("Observador_Common: ERROR al crear CSV '", InpCSVFileName,
            "' err=", GetLastError());
      return;
   }

   FileWrite(handle,
             "event_type",     // 1
             "ticket",         // 2
             "order_type",     // 3
             "lots",           // 4
             "symbol",         // 5
             "open_price",     // 6
             "open_time",      // 7
             "sl",             // 8
             "tp",             // 9
             "close_price",    // 10
             "close_time",     // 11
             "profit",         // 12
             "magic",          // 13
             "comment");       // 14

   FileClose(handle);
}

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("Observador_Common v1.1 inicializado. CSV(COMMON) = ", InpCSVFileName);

   g_prevCount   = 0;
   g_initialized = false;
   ArrayInitialize(g_prevTickets, 0);

   InitCSVIfNeeded();

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("Observador_Common finalizado. reason = ", reason);
}

//+------------------------------------------------------------------+
//| OnTick                                                           |
//+------------------------------------------------------------------+
void OnTick()
{
   int  curTickets[MAX_ORDERS];
   int  curCount = 0;
   ArrayInitialize(curTickets, 0);

   //================= 1) Construir lista de tickets actuales ============
   int total = OrdersTotal();
   for(int i = 0; i < total && curCount < MAX_ORDERS; i++)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;

      int ticket = OrderTicket();
      curTickets[curCount] = ticket;
      curCount++;
   }

   //================= 1.5) Primera vez: registrar las órdenes ya abiertas
   if(!g_initialized)
   {
      Print("Observador_Common: inicialización. Órdenes abiertas actuales = ", curCount);

      for(int k = 0; k < curCount; k++)
      {
         int t = curTickets[k];
         if(OrderSelect(t, SELECT_BY_TICKET, MODE_TRADES))
         {
            string tipo;
            switch(OrderType())
            {
               case OP_BUY:       tipo = "BUY";       break;
               case OP_SELL:      tipo = "SELL";      break;
               case OP_BUYLIMIT:  tipo = "BUYLIMIT";  break;
               case OP_SELLLIMIT: tipo = "SELLLIMIT"; break;
               case OP_BUYSTOP:   tipo = "BUYSTOP";   break;
               case OP_SELLSTOP:  tipo = "SELLSTOP"; break;
               default:           tipo = "OTRO";      break;
            }

            AppendEventToCSV("OPEN",
                             t,
                             tipo,
                             OrderLots(),
                             OrderSymbol(),
                             OrderOpenPrice(),
                             OrderOpenTime(),
                             OrderStopLoss(),
                             OrderTakeProfit(),
                             0.0,
                             0,
                             0.0,
                             OrderMagicNumber(),
                             OrderComment());
         }

         g_prevTickets[k] = t;
      }

      g_prevCount   = curCount;
      g_initialized = true;
      return;
   }

   //================= 2) Detectar nuevas APERTURAS ======================
   for(int j = 0; j < curCount; j++)
   {
      int t = curTickets[j];
      if(!TicketInArray(t, g_prevTickets, g_prevCount))
      {
         if(OrderSelect(t, SELECT_BY_TICKET, MODE_TRADES))
         {
            string tipo;
            switch(OrderType())
            {
               case OP_BUY:       tipo = "BUY";       break;
               case OP_SELL:      tipo = "SELL";      break;
               case OP_BUYLIMIT:  tipo = "BUYLIMIT";  break;
               case OP_SELLLIMIT: tipo = "SELLLIMIT"; break;
               case OP_BUYSTOP:   tipo = "BUYSTOP";   break;
               case OP_SELLSTOP:  tipo = "SELLSTOP"; break;
               default:           tipo = "OTRO";      break;
            }

            AppendEventToCSV("OPEN",
                             t,
                             tipo,
                             OrderLots(),
                             OrderSymbol(),
                             OrderOpenPrice(),
                             OrderOpenTime(),
                             OrderStopLoss(),
                             OrderTakeProfit(),
                             0.0,
                             0,
                             0.0,
                             OrderMagicNumber(),
                             OrderComment());
         }
      }
   }

   //================= 3) Detectar CIERRES (tickets que ya no están) =====
   for(int p = 0; p < g_prevCount; p++)
   {
      int oldTicket = g_prevTickets[p];

      if(!TicketInArray(oldTicket, curTickets, curCount))
      {
         if(OrderSelect(oldTicket, SELECT_BY_TICKET, MODE_HISTORY))
         {
            string tipo;
            switch(OrderType())
            {
               case OP_BUY:       tipo = "BUY";       break;
               case OP_SELL:      tipo = "SELL";      break;
               case OP_BUYLIMIT:  tipo = "BUYLIMIT";  break;
               case OP_SELLLIMIT: tipo = "SELLLIMIT"; break;
               case OP_BUYSTOP:   tipo = "BUYSTOP";   break;
               case OP_SELLSTOP:  tipo = "SELLSTOP"; break;
               default:           tipo = "OTRO";      break;
            }

            AppendEventToCSV("CLOSE",
                             oldTicket,
                             tipo,
                             OrderLots(),
                             OrderSymbol(),
                             OrderOpenPrice(),
                             OrderOpenTime(),
                             OrderStopLoss(),
                             OrderTakeProfit(),
                             OrderClosePrice(),
                             OrderCloseTime(),
                             OrderProfit(),
                             OrderMagicNumber(),
                             OrderComment());
         }
      }
   }

   //================= 4) Actualizar lista previa ========================
   g_prevCount = curCount;
   for(int m = 0; m < curCount; m++)
      g_prevTickets[m] = curTickets[m];
}

