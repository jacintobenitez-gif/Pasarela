//+------------------------------------------------------------------+
//|                                            LibreriaTriggerOI.mq4 |
//|                                  Copyright 2025, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property library
#property copyright "Copyright 2025, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict

//Variables Globales
double version = 1.00;
string Par = Symbol();
int Digitos = (int)MarketInfo(Par, MODE_DIGITS);

//Direcciones
int DIR_NODIR  = 0;
int DIR_LARGOS = 1;
int DIR_CORTOS = -1;

//Trazas
string Traza0 = "";
string Traza1 = "";
string Traza2 = "";
string Traza3 = "";
string Traza4 = "";

int Log = 1;

//Inversion
double capital   = 0;   
double inversion  = 0;                        
double valorLote  = 0; 
double lotespotencialesainvertir = 0; 
string commentSalida = "";
int    numerooperaciones = 0; 
double miniLotes = 0;
int OperacionesAbiertas = 0;

//ZigZag
double   ZZAux[];
datetime ZZAuxTime[];
double   ZZAuxFractal[];
int ZZAuxDirFractal[];
int FRACTAL_UP = 1;
int FRACTAL_DN = -1;
int FRACTAL_NODIRECTION = -1000;

bool LecturaMercado = true;
bool SalidaMercado = false;



//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      FUNCIONES NEGOCIO BASICAS
//-------------------------------------------------------------------+
//+------------------------------------------------------------------+
void ZigZagFractal(string sMarket, ENUM_TIMEFRAMES iPeriodo, int ZZPeriodo, int Deviation,
int Backstep, int iIteraciones)
{
   int    n = 0;
   int    i = 0;
   double zig = 0.0;
   bool   bSalida = false;

   if (iIteraciones < 1) iIteraciones = 1;

   ArrayResize(ZZAux,     iIteraciones);
   ArrayResize(ZZAuxTime, iIteraciones);
   ArrayResize(ZZAuxFractal, iIteraciones);
   ArrayResize(ZZAuxDirFractal, iIteraciones);
   ArrayInitialize(ZZAux,     0.0);
   ArrayInitialize(ZZAuxTime, 0);
   ArrayInitialize(ZZAuxFractal, 0);
   ArrayInitialize(ZZAuxDirFractal, 0);

   // Recorre desde la barra más reciente hacia atrás
   while ((n < iIteraciones) && (bSalida == false))
   {
      zig = iCustom(sMarket, iPeriodo, "ZigZag", ZZPeriodo, Deviation, Backstep, 0, i);
      
      if(zig > 0.0)
      {
         ZZAux[n]     = zig;                         // precio pivote
         ZZAuxTime[n] = iTime(sMarket, iPeriodo, i); // tiempo pivote
         
         double up  = iFractals(Par, iPeriodo, MODE_UPPER, i);
         double dn  = iFractals(Par, iPeriodo, MODE_LOWER, i);

         if ((up > 0) && (up == zig))
         {
            ZZAuxFractal[n] = up;
            ZZAuxDirFractal[n] = FRACTAL_UP;
         }

         if ((dn > 0) && (dn == zig))
         {
            ZZAuxFractal[n] = dn;
            ZZAuxDirFractal[n] = FRACTAL_DN;
         }
            
         if ((up == 0) && (dn == 0))
         {
            ZZAuxFractal[n] = 0;
            ZZAuxDirFractal[n] = FRACTAL_NODIRECTION;
         }
         
         n++;
      }
      
      i++;
      
      if (i > 2000) bSalida = true;
   }
}


//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      FUNCIONES BASICAS
//-------------------------------------------------------------------+
//+------------------------------------------------------------------+

void LotsForMarginPercent(double percent, int &norders, double &minlotes)
{
   if (Log == 1) Traza1 = "";
   if (Log == 1) Trazas(" LotsForMarginPercent: " + DoubleToStr(percent, Digitos), Traza1);    

   capital    = AccountEquity();   
   inversion  = capital * percent;                      // p.ej., 0.70
   valorLote  = MarketInfo(Par, MODE_MARGINREQUIRED);   // margen por 1.00 lot

   double lotsRaw = inversion / valorLote;

   // Ajuste a los límites/step del símbolo
   double minL = MarketInfo(Par, MODE_MINLOT);
   double maxL = MarketInfo(Par, MODE_MAXLOT);
   double step = MarketInfo(Par, MODE_LOTSTEP);

   lotespotencialesainvertir = MathFloor(lotsRaw / step) * step;   

   if (Log == 1) Trazas(" LotsForMarginPercent: Capital: " + DoubleToStr(capital, Digitos) + " Inversion: " + DoubleToStr(inversion, Digitos), Traza1);
   if (Log == 1) Trazas(" Valor Lote: " + DoubleToStr(valorLote, Digitos) + " Lotes a Invertir: " + DoubleToStr(lotespotencialesainvertir, Digitos), Traza1);

   // aquí hacías la división en 10
   minlotes = lotespotencialesainvertir / 10;

   // PARCHE: ajustar el mini-lote al step permitido y al mínimo
   minlotes = MathFloor(minlotes / step) * step;
   if (minlotes < minL) minlotes = minL;

   if (minlotes > minL)
   {
      norders = 10;
   }
   else
   {
      norders = 1;
   }

   if (Log == 1) Trazas(" Lote MIN: " + DoubleToStr(minL, Digitos) + " Lote MAX: " + DoubleToStr(maxL, Digitos) + " Lote STEP: " + DoubleToStr(step, Digitos), Traza1);
   if (Log == 1) Trazas(" Mini Lote: " + DoubleToStr(minlotes, Digitos) + " Operaciones: " + DoubleToStr(norders, Digitos), Traza1);
   
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      FUNCIONES ACCESO A MERCADO

int ExecMarket(int dir, int maxOps, double lots, string comment = "")
{

   RefreshRates();

   int    slippage   = 3;      // puedes ajustar
   int    k          = 0;
   int    opened     = 0;
   
   for(k=0; k<maxOps; k++)
   {
      RefreshRates();
      double price = 0, tp = 0, sl = 0;
      int    type = 0;
      int magic = 31071974;

      if (dir == DIR_LARGOS)
      {
         type  = OP_BUY;
         price = NormalizeDouble(Ask, Digitos);
      }
      else if (dir == DIR_CORTOS)
      {
         type  = OP_SELL;
         price = NormalizeDouble(Bid, Digitos);
      }

      CalcularTPySL(Par, type, price, 2, 0, tp, sl);
      if (Log == 1) Trazas("TP:" + DoubleToStr(tp) + " SL: " + DoubleToStr(sl), Traza2); 

      // Enviar orden
      int ticket = OrderSend(Par, type, lots, price, slippage, sl, tp, comment, magic, 0, clrNONE);
      
      if(ticket < 0)
      {
         if (Log == 1) Trazas("Par: " + Par + " OrderSend error" + IntegerToString(GetLastError()), Traza2); 
      }
      else
      {
         if (Log == 1)  Trazas("Par: " + Par + " Tickect nuevo: " + IntegerToString(ticket), Traza2); 
         opened++;
      }
   }

   return (opened);
}


//---------------------------------------------------------------
// Calcula el Take Profit a partir de un número de pips objetivo
//
// symbol     -> par (ej. Symbol())
// orderType  -> OP_BUY u OP_SELL
// entryPrice -> precio de entrada
// profitPips -> pips que quieres ganar
//
// Devuelve: precio de TP normalizado a los dígitos del símbolo
//---------------------------------------------------------------
void CalcularTPySL(string symbol, int orderType, double entryPrice, 
                   double profitPips, double lossPips,
                   double &tp, double &sl)
{
   double pipSize = GetPipSize(symbol);

   // Ajuste especial para ORO:
   // Si el símbolo contiene "XAU", interpretamos profitPips/lossPips como dólares (1.0)
   if(StringFind(symbol, "XAU") != -1)
      pipSize = 1.0;

   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   tp = 0.0;
   sl = 0.0;

   if(orderType == OP_BUY)
   {
      // TP solo si profitPips > 0
      if(profitPips > 0)
         tp = NormalizeDouble(entryPrice + profitPips * pipSize, digits);

      // SL solo si lossPips > 0; si es 0, dejamos sl = 0.0 (sin SL)
      if(lossPips > 0)
         sl = NormalizeDouble(entryPrice - lossPips * pipSize, digits);
   }
   else if(orderType == OP_SELL)
   {
      if(profitPips > 0)
         tp = NormalizeDouble(entryPrice - profitPips * pipSize, digits);

      if(lossPips > 0)
         sl = NormalizeDouble(entryPrice + lossPips * pipSize, digits);
   }
   // Si llega otro tipo de orden, tp y sl se quedan en 0.0
}

//---------------------------------------------
// Devuelve el tamaño de 1 pip para el símbolo
//---------------------------------------------
double GetPipSize(string symbol)
{
   double point  = MarketInfo(symbol, MODE_POINT);
   int    digits = (int)MarketInfo(symbol, MODE_DIGITS);

   // Brokers de 5 dígitos (EURUSD 1.23456) o 3 dígitos (USDJPY 123.456)
   if(digits == 3 || digits == 5)
      return point * 10.0;

   // Brokers de 2 o 4 dígitos
   return point;
}

int CierreOrdenes(string targetComment)
{
   RefreshRates();
   int contador = 0;

   if (Log == 1) Trazas(" CierreOrdenes: TargetComment: " + targetComment, Traza3);

   for(int i = OrdersTotal()-1; i >= 0; i--)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         // Comparación EXACTA (sensible a mayúsculas/minúsculas)
//         if (Log == 1) Trazas("\nOrderComment: " + OrderComment(), Traza3);

         if(OrderComment() == targetComment)
         {
            int ticket = OrderTicket();
            int type   = OrderType();
            RefreshRates();
            double price = (type==OP_BUY) ? Bid : Ask;
            bool ok = OrderClose(ticket, OrderLots(), NormalizeDouble(price, Digitos), 3);
            if (ok)
               contador++;   
            else
               if (Log == 1) Trazas("\nOrderClose error ticket=" + IntegerToString(ticket) +  " Error code=" + IntegerToString(GetLastError()), Traza3); 
         }
      }
   }

   if (Log == 1) Trazas(" CierreOrdenes: Ordenes cerradas: " + IntegerToString(contador), Traza3);  
    
   return(contador);   
}

// Cuenta cuántas órdenes ABIERTAS hay con un comentario EXACTO (y del símbolo actual)
int SalidaporTPSL(string targetComment)
{
   RefreshRates();
   int count = 0;

   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         if(OrderComment() == targetComment)
            count++;
      }
   }
   return count;
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      FUNCIONES AUXILIARES
//-------------------------------------------------------------------+
//+------------------------------------------------------------------+

void Trazas(string cadena, string &Textofinal)
{
   string cadenafinal = "\n" + NowHMSStr() + cadena;
   Textofinal = Textofinal + cadenafinal;
}

string NowHMSStr()
{
   return TimeToString(TimeCurrent(), TIME_SECONDS); // "YYYY.MM.DD HH:MM:SS"
}

