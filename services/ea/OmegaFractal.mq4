//+------------------------------------------------------------------+
//|                                                OmegaFractal4.mq4 |
//|                                  Copyright 2025, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict

input ENUM_TIMEFRAMES PeriodoMICRO = PERIOD_M1;
input ENUM_TIMEFRAMES PeriodoMESO = PERIOD_M5;
input ENUM_TIMEFRAMES PeriodoFractal = PERIOD_M30;

input bool PintarHistorico = true;
input int  NumeroFractalesPintarHistorico = 20;
input bool PintarLineaVertical = true;
input bool Real = false;

//Variables Globales
int MV32 = 32;
int MV8 = 8;
string Par = Symbol();
int Digitos = (int)MarketInfo(Par, MODE_DIGITS);
bool PintarUnaVez = false;
double FractalNuevo = 0;
double FractalAnterior = 0;
bool FractalValido = false;
bool LecturaMercado = true;
bool EntradaMercado = false;
bool SalidaMercado = false;

//ZigZag
double   ZZAux[];
datetime ZZAuxTime[];

//Direcciones
int DIR_NODIR  = 0;
int DIR_LARGOS = 1;
int DIR_CORTOS = -1;
int Direccion = DIR_NODIR;

//Trazas
string Traza1 = "";
string Traza2 = "";

//Patrones
bool ActivadoPatronImpulsoOnda3M32 = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//---
   if ((PintarHistorico) && (PintarLineaVertical) && (!PintarUnaVez))
   {
      // Borra todas las OBJ_VLINE del gráfico (todas las subventanas)
      DeleteAllVLines();
      DeleteAllPoints();
      GetLastFractalsHistory(NumeroFractalesPintarHistorico);
      PintarUnaVez = true;
   }
   
//---
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
//---

   if (LecturaMercado)
   {
      FractalNuevo = GetLastFractalNow(Direccion);
      
      if (FractalNuevo != FractalAnterior)
      {
         //Encontramos nuevo fractal y pintamos linea correspondiente para ayuda visual
         //en la lectura.
         
         FractalAnterior = FractalNuevo;
         FractalValido = false;
         
         if (PintarLineaVertical)
         { 
            GetFractalinMICRO(FractalAnterior, FractalValido); 
         } 

         //Con el nuevo fractal, valido, procedo a buscar nuevas oportunidades de negocio.  
         if ((FractalValido) && (Real))
         {    
            LecturaMercado = false;
            EntradaMercado = true;
            SalidaMercado = false;
         }

      }
   }
   else if (EntradaMercado)
   {
      double StopLoss = 0;
      
      //Busqueda de oportunidades de negocio.
      if (PatronImpulsoOnda3M32(FractalAnterior, Direccion, StopLoss))
      {
         //Ejecutas orden en el mercado
         if (ExecMarket(Direccion, 1, StopLoss, 0.1, Par + "-P1") > 0)
         {
            LecturaMercado = false;
            EntradaMercado = false;
            SalidaMercado = true;
            ActivadoPatronImpulsoOnda3M32 = true;            
         }
      }
   }
   else if (SalidaMercado)
   {
      //Verificar que todas las operaciones se cerraron
      //damos paso a la lectura del mercado
      
      if (ActivadoPatronImpulsoOnda3M32)
      {
         //Cerrar ordenes mercado.
         if (SalidaPatronImpulsoOnda3M32(FractalAnterior, Direccion))  
         {
            // Cierre por TP lógico (condición de salida)
            string commentSalida = Par + "-P1";
            int cerradas = CierreOrdenes(commentSalida);
   
            // Reset de estado si ya no quedan órdenes con ese comentario
            if (cerradas > 0)
            {
               ActivadoPatronImpulsoOnda3M32 = false;
               LecturaMercado = true;
               EntradaMercado = false;
               SalidaMercado = false;               
            }
         } 
      }
   }
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      PATRONES BASICOS

bool PatronImpulsoOnda3M32(double dFractal, int dir, double &sl)
{
   //Patron basado en buscar en PeriodoMICRO, Ondas 2 u Ondas 3 consecutivas, en impulso, a 
   //partir del precio del fractal encontrado entre PeriodoFractal y PeriodoMICRO.
   bool bPatronOnda3M32 = false;
   sl = 0;
   
   //Leyendo las ultima posición del periodo MICRO
   ZigZag(Par, PeriodoMICRO, MV32, 4);
   // justo después de ZigZag(Par, PeriodoMICRO, MV32, 4);
   if(ZZAux[0] == 0.0 || ZZAux[1] == 0.0 || ZZAux[2] == 0.0) return false;
   
   if (dir == DIR_LARGOS)
   {
      if ((ZZAux[2] == dFractal) && (ZZAux[0] < ZZAux[1]) 
      && (ZZAux[1] > ZZAux[2]))
      {
         double ZZR2 = ZZAux[2];
         double ZZR1 = ZZAux[1];
         double ZZR0 = ZZAux[0];

         //Leyendo las ultima posición del PeriodoMESO
         //para comparar las con las ondas M32 del PeriodoMICRO
         ZigZag(Par, PeriodoMESO, MV8, 3);
         // tras ZigZag(Par, PeriodoMESO, MV8, 3);
         if(ZZAux[0] == 0.0 || ZZAux[1] == 0.0 || ZZAux[2] == 0.0) return false;

         
         if ((ZZR0 == ZZAux[0]) && (ZZR1 == ZZAux[1]) && (ZZR2 == ZZAux[2]))
         {
            //ONDA 2
            if (DirEMA1vsEMA5(PeriodoMICRO, dir) && DirWPR(PeriodoMICRO, dir) && DirCCI(PeriodoMICRO, dir))
            {
               //Trigger Operacion Largos
               bPatronOnda3M32 = true;
               sl = ZZR0;
            }         
         }         
      }
   }
   else if (dir == DIR_CORTOS)
   {
      if ((ZZAux[2] == dFractal) && (ZZAux[0] > ZZAux[1]) 
      && (ZZAux[1] < ZZAux[2]))
      {
         double ZZR2 = ZZAux[2];
         double ZZR1 = ZZAux[1];
         double ZZR0 = ZZAux[0];

         //Leyendo las ultima posición del PeriodoMESO
         //para comparar las con las ondas M32 del PeriodoMICRO
         ZigZag(Par, PeriodoMESO, MV8, 3);
         // tras ZigZag(Par, PeriodoMESO, MV8, 3);
         if(ZZAux[0]==0.0 || ZZAux[1]==0.0 || ZZAux[2]==0.0) return false;
         
         if ((ZZR0 == ZZAux[0]) && (ZZR1 == ZZAux[1]) && (ZZR2 == ZZAux[2]))
         {
            //ONDA 2
            if (DirEMA1vsEMA5(PeriodoMICRO, dir) && DirWPR(PeriodoMICRO, dir) && DirCCI(PeriodoMICRO, dir))
            {
               //Trigger Operacion Largos
               bPatronOnda3M32 = true;
               sl = ZZR0;
            }         
         }         
      }
   }
   
   return(bPatronOnda3M32);
}

bool SalidaPatronImpulsoOnda3M32(double dFractal, int dir)
{
   bool bSalidaPatronImpulsoOnda3M32 = false;

   //Leyendo las ultima posición del periodo MICRO
   ZigZag(Par, PeriodoMICRO, MV32, 4);
// después de ZigZag(Par, PeriodoMICRO, MV32, 4);
   if(ZZAux[0] == 0.0 || ZZAux[1] == 0.0 || ZZAux[2] == 0.0 || ZZAux[3] == 0.0) return false;
   
   if (dir == DIR_LARGOS)
   {
      if ((ZZAux[3] == dFractal) && (ZZAux[0] > ZZAux[1])
      && (ZZAux[1] < ZZAux[2]) && (ZZAux[2] > ZZAux[3]))
      {
         //ONDA 3
         bSalidaPatronImpulsoOnda3M32 = true;
      }
   }
   else if (dir == DIR_CORTOS)
   {
      if ((ZZAux[3] == dFractal) && (ZZAux[0] < ZZAux[1])
      && (ZZAux[1] > ZZAux[2]) && (ZZAux[2] < ZZAux[3]))
      {
         //ONDA 3
         bSalidaPatronImpulsoOnda3M32 = true;
      }      
   }
      
   return(bSalidaPatronImpulsoOnda3M32);
}

// Devuelve la dirección de EMA(1) vs  EMA(5) en el TF.
bool DirEMA1vsEMA5(ENUM_TIMEFRAMES tf, int dir)
{
   bool salida = false;

   int tfconvertido = ConversorTF(tf);
   
   double ema1   = iMA(Par, tfconvertido, 1, 0, MODE_EMA,   PRICE_CLOSE, 0);
   double ema5   = iMA(Par, tfconvertido, 5, 0, MODE_EMA,   PRICE_CLOSE, 0);

   if ((dir == DIR_LARGOS) && (ema1 > ema5))
      salida = true;
   else if ((dir == DIR_CORTOS) && (ema1 < ema5))
      salida = true;
   else
      salida = false;   
   
   return salida;

}

// Devuelve la dirección según Williams %R (periodo 8) en el TF indicado.
// - Si WPR >= -20  y dir==DIR_LARGOS -> true
// - Si WPR <= -80  y dir==DIR_CORTOS -> true
// - En otro caso -> false
bool DirWPR(ENUM_TIMEFRAMES tf, int dir)
{
   int tfconvertido = ConversorTF(tf);
   int period = 8; // estándar de Williams %R
   double wpr = iWPR(Par, tfconvertido, period, 0); // barra actual

   if(wpr == EMPTY_VALUE) 
      return false;

   if((dir == DIR_LARGOS) && (wpr >= -20.0))
      return true;

   if((dir == DIR_CORTOS) && (wpr <= -80.0))
      return true;

   return false;
}

// Devuelve la dirección según CCI (periodo 8) en el TF indicado.
// - Si CCI >=  +100 y dir==DIR_LARGOS -> true
// - Si CCI <=  -100 y dir==DIR_CORTOS -> true
// - En otro caso -> false
bool DirCCI(ENUM_TIMEFRAMES tf, int dir)
{
   int tfconvertido = ConversorTF(tf);
   int period = 8; // estándar CCI
   double cci = iCCI(Par, tfconvertido, period, PRICE_TYPICAL, 0); // barra actual

   if(cci == EMPTY_VALUE)
      return false;

   if((dir == DIR_LARGOS) && (cci >= 100.0))
      return true;

   if((dir == DIR_CORTOS) && (cci <= -100.0))
      return true;

   return false;
}

//+------------------------------------------------------------------+
double GetLastFractalNow(int &DireccionActual)
{
   int dir = DIR_NODIR;
   int contador = 0;
   int lookback = 1;
   double Fractal = 0;

   // Recorremos barras desde la más reciente (shift=0) hacia atrás
   int tfconvertido = ConversorTF(PeriodoFractal);
   int total = iBars(Par, tfconvertido);         
   for (int i = 0; i < total; i++)
   {
      double up  = iFractals(Par, tfconvertido, MODE_UPPER, i);
      double dn  = iFractals(Par, tfconvertido, MODE_LOWER, i);
      
      if (up > 0)
      {
         Fractal = up;
         DireccionActual = DIR_CORTOS;
         contador++;          
      }
      else if (dn > 0)
      {
         Fractal = dn;
         DireccionActual = DIR_LARGOS; 
         contador++;
      }      
      
      if (contador >= lookback)
         break;
      
   }

   return (Fractal);
   
}


//+------------------------------------------------------------------+
void GetLastFractalsHistory(int lookback = 1)
{
   int contador = 0;
   double Fractal = 0;

   // Recorremos barras desde la más reciente (shift=0) hacia atrás
   int tfconvertido = ConversorTF(PeriodoFractal);
   int total = iBars(Par, tfconvertido);         
   for (int i = 0; i < total; i++)
   {
      double up  = iFractals(Par, tfconvertido, MODE_UPPER, i);
      double dn  = iFractals(Par, tfconvertido, MODE_LOWER, i);
      
      if (up > 0)
      {
         Fractal = up;
         bool dummy=false;
         if (PintarLineaVertical) 
            GetFractalinMICRO(Fractal, dummy);  
         contador++;          
      }
      else if (dn > 0)
      {
         Fractal = dn;
         bool dummy=false;
         if (PintarLineaVertical) 
            GetFractalinMICRO(Fractal, dummy);
         contador++;
      }      
      
      if (contador >= lookback)
         break;
      
   }   
}

void GetFractalinMICRO(double Price, bool &FValido)
{
   // Recorremos barras desde la más reciente (shift=0) hacia atrás
   int tfconvertido = ConversorTF(PeriodoMICRO);   
   int total = iBars(Par, tfconvertido);     
   FValido = false;
 
   for (int i = 0; i < total; i++)
   {
      double up  = iFractals(Par, tfconvertido, MODE_UPPER, i);
      double dn  = iFractals(Par, tfconvertido, MODE_LOWER, i);
   
      
      if (NormalizeDouble(up, Digitos) == NormalizeDouble(Price, Digitos))
      {
         // ← aquí obtienes la hora/minuto/segundo del fractal M1 (vela central del patrón)
         datetime t_m1 = iTime(Par, tfconvertido, i);  
         
         if (IsExactZigZagM1At(Price, t_m1, 32, 5, 3)) 
         {
            DrawVLine(t_m1, clrRed);
            FValido = true;
         }
         else
         {
            DrawVLine(t_m1, clrOrange);
            FValido = false;
         }
         
         break;      
      }
      else if (NormalizeDouble(dn, Digitos) == NormalizeDouble(Price, Digitos))
      {
         // ← aquí obtienes la hora/minuto/segundo del fractal M1 (vela central del patrón)
         datetime t_m1 = iTime(Par, tfconvertido, i);  
          
         if (IsExactZigZagM1At(Price, t_m1, 32, 5, 3)) 
         {
            DrawVLine(t_m1, clrGreen);
            FValido = true;            
         }           
         else
         {
            DrawVLine(t_m1, clrOrange);
            FValido = false;
         }
            
         break;
      }
   }
}

// ===================== ZigZag (núcleo con arrays ZZAux/ZZAuxTime) ======================
void ZigZag(string sMarket, ENUM_TIMEFRAMES iPeriodo, int ZZPeriodo, int iIteraciones)
{
   int    n = 0;
   int    i = 0;
   double zig = 0.0;
   bool   bSalida = false;

   if(iIteraciones < 1) iIteraciones = 1;

   ArrayResize(ZZAux,     iIteraciones);
   ArrayResize(ZZAuxTime, iIteraciones);
   ArrayInitialize(ZZAux,     0.0);
   ArrayInitialize(ZZAuxTime, 0);

   // Recorre desde la barra más reciente hacia atrás
   while ((n < iIteraciones) && (bSalida == false))
   {
      zig = iCustom(sMarket, iPeriodo, "ZigZag", ZZPeriodo, 5, 3, 0, i);
      if(zig > 0.0)
      {
         ZZAux[n]     = zig;                         // precio pivote
         ZZAuxTime[n] = iTime(sMarket, iPeriodo, i); // tiempo pivote
         n++;
      }
      i++;
      if (i > 3000) bSalida = true;
   }
}


bool IsExactZigZagM1At(double Price, datetime t_m1, int zzDepth=32, int zzDeviation=5, int zzBackstep=3)
{

   int tfconvertido = ConversorTF(PeriodoMICRO);   
   int shift = iBarShift(Par, tfconvertido, t_m1, true);
   if(shift < 0) return false;

   
   // Buffer 0 = precio en vértices (sirve para UP y DOWN)
   double zz = iCustom(Par, tfconvertido, "ZigZag",
                       zzDepth, zzDeviation, zzBackstep,
                       0, shift);

   if(zz == 0.0 || zz == EMPTY_VALUE) 
   {  
      return false;
   }
   
   return (true);
}

void DrawVLine(datetime t_m1, color c=clrDodgerBlue)
{
   string name = StringFormat("Fractal_%s_%s", Par, TimeToString(t_m1, TIME_DATE|TIME_MINUTES|TIME_SECONDS));
   
   if(ObjectFind(0, name) >= 0) return;
   
   ObjectCreate(0, name, OBJ_VLINE, 0, t_m1, 0);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   
}

int ConversorTF(ENUM_TIMEFRAMES tf)
{
   int tfconvertido = 0;
   
   if (tf == PERIOD_M1)
      tfconvertido = PERIOD_M1;
   else if (tf == PERIOD_M5)
      tfconvertido = PERIOD_M5;
   else if (tf == PERIOD_M15)
      tfconvertido = PERIOD_M15;
   else if (tf == PERIOD_M30)
      tfconvertido = PERIOD_M30;
   else if (tf == PERIOD_H1)
      tfconvertido = PERIOD_H1;
   else if (tf == PERIOD_H4)
      tfconvertido = PERIOD_H4;
   
   return(tfconvertido);
   
}

void DeleteAllVLines()
{
   // chart_id=0 (actual), sub_window=-1 (todas), object_type=OBJ_VLINE
   ObjectsDeleteAll(0, -1, OBJ_VLINE);
}

void DeleteAllPoints()
{
   for(int i = ObjectsTotal()-1; i >= 0; i--)
   {
      string name = ObjectName(i);
      if(ObjectType(name) == OBJ_ARROW)
      {
         int code = (int)ObjectGetInteger(0, name, OBJPROP_ARROWCODE);
         if(code == 159)   // nuestro "bullet" Wingdings
            ObjectDelete(0, name);
      }
   }
}


// Punto genérico en el tiempo y precio indicados (usa un "bullet" Wingdings 159)
void PlotPointAt(double price, color c)
{
   double   p   = NormalizeDouble(price, Digitos);
   datetime tt  = TimeCurrent();

   // nombre robusto: Symbol + epoch + contador si ya existe
   static int seq = 0;
   string base = StringFormat("%s_%s_%d", "PT", Par, (int)tt);
   string name = base;

   // evita colisión si pintas varios en el mismo segundo
   while(ObjectFind(0, name) >= 0)
   { 
      seq++; 
      name = StringFormat("%s_%d", base, seq); 
   }

   ObjectCreate(0, name, OBJ_ARROW, 0, tt, p);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 4);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, 159);     // bullet
   ObjectSetInteger(0, name, OBJPROP_BACK, false);        // delante
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);  // no seleccionable
   
}


// Abre X órdenes de mercado por dirección.
// - dir: DIR_LARGOS o DIR_CORTOS
// - maxOps: máximo de órdenes abiertas permitidas para esa dirección (símbolo actual)
// - lots: tamaño de lote para cada orden nueva
// - sl: vendrá del exterior.
// - comment: comentario opcional de la orden.
// Devuelve numero de operaciones abiertas.
int ExecMarket(int dir, int maxOps, double sl = 0, double lots = 0.1, string comment = "")
{

   RefreshRates();

   int    slippage   = 3;      // puedes ajustar
   int    k          = 0;
   int    opened     = 0;
   double sl_price   = NormalizeDouble(sl, Digitos);
   
   for(k=0; k<maxOps; k++)
   {
      RefreshRates();
      double price, tp;
      int    type;
      int magic = 31071974;

      if(dir == DIR_LARGOS)
      {
         type  = OP_BUY;
         price = NormalizeDouble(Ask, Digitos);
         tp    = 0.0;
      }
      else // DIR_CORTOS
      {
         type  = OP_SELL;
         price = NormalizeDouble(Bid, Digitos);
         tp    = 0.0;
      }

      // Enviar orden
      int ticket = OrderSend(Par, type, lots, price, slippage, sl_price, tp, comment, magic, 0, clrNONE);
      if(ticket < 0)
      {
         // Si falla, intentamos seguir con el resto (por si es un fallo puntual)
         // Puedes loguear el error:
         Print("OrderSend error: ", GetLastError());
      }
      else
         opened++;
   }

   return (opened);
}


int CierreOrdenes(string targetComment)
{
   RefreshRates();
   int contador = 0;

   for(int i = OrdersTotal()-1; i >= 0; i--)
   {
      if(OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
      {
         // Comparación EXACTA (sensible a mayúsculas/minúsculas)
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
               Print("OrderClose error ticket=", ticket, " code=", GetLastError());
         }
      }
   }
   
   return(contador);   
}
