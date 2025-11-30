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
double R0M15 = 0;
double R1M15 = 0;
double R2M15 = 0;
double R3M15 = 0;


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
int TakeProfit = 3;

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

//--------------------------------------------------------------
// Dirección por alineación de 3 Williams %R
// Devuelve:
//   DIR_CORTOS  si los 3 %R < -50
//   DIR_LARGOS  si los 3 %R > -50
//   0           en cualquier otro caso (neutro / mixto / sin datos)
//--------------------------------------------------------------
int GetDireccionPorWPR(string symbol,
                       int timeframe,
                       int period1,
                       int period2,
                       int period3,
                       int shift = 0)
{
   double w1 = iWPR(symbol, timeframe, period1, shift);
   double w2 = iWPR(symbol, timeframe, period2, shift);
   double w3 = iWPR(symbol, timeframe, period3, shift);

   // Si aún no hay datos suficientes, devolvemos neutro
   if(w1 == EMPTY_VALUE || w2 == EMPTY_VALUE || w3 == EMPTY_VALUE)
      return 0;

   // Todos por debajo de -50 → DIR_CORTOS
   if(w1 < -50.0 && w2 < -50.0 && w3 < -50.0)
      return DIR_CORTOS;

   // Todos por encima de -50 → DIR_LARGOS
   if(w1 > -50.0 && w2 > -50.0 && w3 > -50.0)
      return DIR_LARGOS;

   // Mezcla → sin dirección clara
   return 0;
}

int GetDireccionBB_EMA_M30_H1()
{
   int iGetDireccionBB_EMA_M30_H1 = DIR_NODIR;

   double ema5_curr = iMA(Par, PERIOD_M30, 5, 0, MODE_EMA, PRICE_CLOSE, 0);
   double bbM30_curr = iBands(Par, PERIOD_M30, 8, 2.0, 0, PRICE_CLOSE, MODE_MAIN, 0);
   
   bool largos_M30 = (ema5_curr > bbM30_curr);
   bool cortos_M30 = (ema5_curr < bbM30_curr);

   double ema2_curr = iMA(Par, PERIOD_H1, 2, 0, MODE_EMA, PRICE_CLOSE, 0);
   double bbH1_curr = iBands(Par, PERIOD_H1, 4, 2.0, 0, PRICE_CLOSE, MODE_MAIN, 0);

   // Cruce alcista en H1: antes por debajo/igual, ahora por encima
   bool largos_H1 = (ema2_curr > bbH1_curr);
   bool cortos_H1 = (ema2_curr < bbH1_curr);
   
   if ((largos_M30) && (largos_H1))
   {
      iGetDireccionBB_EMA_M30_H1 = DIR_LARGOS;   
   }
   else if ((cortos_M30) && (cortos_H1))
   {
      iGetDireccionBB_EMA_M30_H1 = DIR_CORTOS;      
   }
   
   return(iGetDireccionBB_EMA_M30_H1);
         
}
//-------------------------------------------------------------
// Devuelve la dirección según dos estocásticos en M15:
//  - Estocástico (8,3,3)
//  - Estocástico (16,3,3)
// Regla:
//   Si ambos tienen MAIN > 50 y MAIN > SIGNAL  -> DIR_LARGOS
//   En cualquier otro caso                      -> DIR_CORTOS
//
// Nota: se usa la vela cerrada (shift = 1)
//       Se asume que DIR_LARGOS y DIR_CORTOS están definidos
//-------------------------------------------------------------
int GetDireccionPorEstocasticosM15()
{
   int tf       = PERIOD_M15;
   int slowing  = 3;
   int dPeriod  = 3;
   int method   = MODE_SMA;
   int price    = 0;      // Low/High (modo estándar del oscilador estocástico)
   int shift    = 0;      // vela cerrada

   // Estocástico (8,3,3)
   int kPeriod1 = 8;
   double main1   = iStochastic(Par, tf, kPeriod1, slowing, dPeriod,
                                method, price, MODE_MAIN, shift);
   double signal1 = iStochastic(Par, tf, kPeriod1, slowing, dPeriod,
                                method, price, MODE_SIGNAL, shift);

   // Estocástico (16,3,3)
   int kPeriod2 = 16;
   double main2   = iStochastic(Par, tf, kPeriod2, slowing, dPeriod,
                                method, price, MODE_MAIN, shift);
   double signal2 = iStochastic(Par, tf, kPeriod2, slowing, dPeriod,
                                method, price, MODE_SIGNAL, shift);

   bool condicionesLargos =
      (main1 > 50.0 && main2 > 50.0 &&
       main1 > signal1 && main2 > signal2);

   bool condicionesCortos =
      (main1 < 50.0 && main2 < 50.0 &&
       main1 < signal1 && main2 < signal2);

   if(condicionesLargos)
      return DIR_LARGOS;
   else if (condicionesCortos)
      return DIR_CORTOS;
   else 
      return DIR_NODIR;
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

int ExecMarket(int dir, int maxOps, double lots, string comment = "", double sl = 0)
{

   RefreshRates();

   int    slippage   = 3;      // puedes ajustar
   int    k          = 0;
   int    opened     = 0;
   
   for(k=0; k<maxOps; k++)
   {
      RefreshRates();
      double price = 0, tp = 0;
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

      CalcularTP(Par, type, price, TakeProfit, tp);
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

void CalcularTP(string symbol, int orderType, double entryPrice, 
                   double profitPips, double &tp)
{
   double pipSize = GetPipSize(symbol);

   // Ajuste especial para ORO:
   // Si el símbolo contiene "XAU", interpretamos profitPips/lossPips como dólares (1.0)
   if(StringFind(symbol, "XAU") != -1)
      pipSize = 1.0;

   int digits = (int)MarketInfo(symbol, MODE_DIGITS);
   tp = 0.0;

   if(orderType == OP_BUY)
   {
      // TP solo si profitPips > 0
      if(profitPips > 0)
         tp = NormalizeDouble(entryPrice + profitPips * pipSize, digits);
   }
   else if(orderType == OP_SELL)
   {
      if(profitPips > 0)
         tp = NormalizeDouble(entryPrice - profitPips * pipSize, digits);
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

