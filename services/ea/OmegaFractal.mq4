//+------------------------------------------------------------------+
//|                                                       Prueba.mq4 |
//|                                  Copyright 2025, MetaQuotes Ltd. |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2025, MetaQuotes Ltd."
#property link      "https://www.mql5.com"
#property version   "1.00"
#property strict

input bool  PintarSeparadoresDia   = true;
input int   DiasSeparadoresHist    = 1;           // cuántos días hacia atrás
input color ColorSeparadorDia      = clrDimGray;
input int   EstiloSeparadorDia     = STYLE_DOT;
input int   AnchoSeparadorDia      = 3;
input bool  GoLive                 = false;

//ZigZag
double   ZZAux[];
datetime ZZAuxTime[];
double   ZZAuxFractal[];

//Direcciones
int DIR_NODIR  = 0;
int DIR_LARGOS = 1;
int DIR_CORTOS = -1;

//Variables Globales
int MV32_Depth = 32;
int MV8_Depth = 8;
int Deviation = 5;
int Backstep = 3;
string Par = Symbol();
int Digitos = (int)MarketInfo(Par, MODE_DIGITS);
bool NotificacionEnviada = false;
bool LecturaMercado = true;
bool EntradaMercado = false;
bool SalidaMercado = false;
bool PintadoPrecio = false;



//Trazas
string Traza1 = "";
string Traza2 = "";
string Traza3 = "";

//Fractal
double FractalLeido = 0;
double FractalActual = 0;
double StopLoss = 0;

//Patrones
bool ActivadoPatronImpulsoOnda3M32 = false;
int DireccionOnda = DIR_NODIR;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//---
   
//---
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
//---
   if(PintarSeparadoresDia)
      EnsureTodaySeparator();

   if (LecturaMercado)
   {
      FractalLeido = GetLastFractal();
      
      if (FractalLeido != FractalActual)
      {
         FractalActual = FractalLeido;
         //Reset
         Reset();         
      }
      else if (FractalLeido == FractalActual)
      {               
         if (PatronImpulsoOnda3M32(FractalActual,StopLoss, DireccionOnda))
         {
            if (!NotificacionEnviada)
            {
               SendNotification("Hora: " + TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS) + "--> Onda3M32 en par: " + Par + " Direccion: " + IntegerToString(DireccionOnda));
               NotificacionEnviada = true;
            }
            
            ActivadoPatronImpulsoOnda3M32 = true;
            LecturaMercado = false;
            EntradaMercado = true;   
         }    
      }
      
      Comment(Traza1, 
      "\n--------------------------------", 
      Traza2);
   }
   else if (EntradaMercado)
   {      
      //Busqueda de oportunidades de negocio.
      if (ActivadoPatronImpulsoOnda3M32)
      {
         if (!GoLive)
         {
            //Buscar punto de entrada preciso al mercado
            if ((DireccionOnda == DIR_LARGOS) && (!PintadoPrecio))
            {
               PlotBigPointM1(0, clrRed);
               PintadoPrecio = true;
            }
            else if ((DireccionOnda == DIR_CORTOS) && (!PintadoPrecio))
            {
               PlotBigPointM1(1, clrGreen);
               PintadoPrecio = true;
            }
            
            
            LecturaMercado = false;
            EntradaMercado = false;
            SalidaMercado = true;            
         }
         else 
         {         
            //Ejecutas orden en el mercado
            if (ExecMarket(DireccionOnda, 1, StopLoss, 0.1, Par + "-P1") > 0)
            {
               LecturaMercado = false;
               EntradaMercado = false;
               SalidaMercado = true;
               ActivadoPatronImpulsoOnda3M32 = true;            
            }
         }
      }
   
   }
   else if (SalidaMercado)
   {
      LecturaMercado = true;
      EntradaMercado = false;
      SalidaMercado = false;               
   }
}
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      FUNCIONES BASICAS

double GetLastFractal()
{
   Traza1 = "";
   ZigZagFractal(Par, PERIOD_M30, MV8_Depth, 2);
   
   if (ZZAuxFractal[0] == ZZAux[0])
   {  
      if (ZZAux[0] > ZZAux[1])
      {
         //Largos 
         datetime f_TimeMICRO = 0;
         
         if (FindZigZagInMICRO(PERIOD_M30, ZZAux[0], ZZAuxTime[0], PERIOD_M1, f_TimeMICRO))
         {
            DrawVLine(f_TimeMICRO, clrRed); 
         }
         
         Trazas(" Fractal activo UP: " + DoubleToStr(ZZAuxFractal[0])+  " Time: " +TimeToString(ZZAuxTime[0], TIME_DATE | TIME_SECONDS), Traza1);
         return(ZZAux[0]);
      }
      else if (ZZAux[0] < ZZAux[1])
      {
         //Cortos
         datetime f_TimeMICRO = 0;
         
         if (FindZigZagInMICRO(PERIOD_M30, ZZAux[0], ZZAuxTime[0], PERIOD_M1, f_TimeMICRO))
         {
            DrawVLine(f_TimeMICRO, clrGreen); 
         }

         Trazas(" Fractal activo DN: " + DoubleToStr(ZZAuxFractal[0])+  " Time: " +TimeToString(ZZAuxTime[0], TIME_DATE | TIME_SECONDS), Traza1);
         return(ZZAux[0]);
      }
   } 
   else if (ZZAuxFractal[1] == ZZAux[1])
   {
      if (ZZAuxFractal[1] > ZZAuxFractal[0])
      {
         datetime f_TimeMICRO = 0;
         
         if (FindZigZagInMICRO(PERIOD_M30, ZZAuxFractal[1], ZZAuxTime[1], PERIOD_M1, f_TimeMICRO))
         {
            DrawVLine(f_TimeMICRO, clrRed); 
         }      

         Trazas(" Fractal activo UP: " + DoubleToStr(ZZAuxFractal[1])+  " Time: " +TimeToString(ZZAuxTime[1], TIME_DATE | TIME_SECONDS), Traza1);
         return(ZZAuxFractal[1]);
      }
      else
      {
         datetime f_TimeMICRO = 0;
         
         if (FindZigZagInMICRO(PERIOD_M30, ZZAuxFractal[1], ZZAuxTime[1], PERIOD_M1, f_TimeMICRO))
         {
            DrawVLine(f_TimeMICRO, clrGreen); 
         }            

         Trazas(" Fractal activo DN: " + DoubleToStr(ZZAuxFractal[1])+  " Time: " +TimeToString(ZZAuxTime[1], TIME_DATE | TIME_SECONDS), Traza1);
         return(ZZAuxFractal[1]);
      }      
   }
      
   return 0;
}

void ZigZagFractal(string sMarket, ENUM_TIMEFRAMES iPeriodo, int ZZPeriodo, int iIteraciones)
{
   int    n = 0;
   int    i = 0;
   double zig = 0.0;
   bool   bSalida = false;

   if(iIteraciones < 1) iIteraciones = 1;

   ArrayResize(ZZAux,     iIteraciones);
   ArrayResize(ZZAuxTime, iIteraciones);
   ArrayResize(ZZAuxFractal, iIteraciones);
   ArrayInitialize(ZZAux,     0.0);
   ArrayInitialize(ZZAuxTime, 0);
   ArrayInitialize(ZZAuxFractal, 0);

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

         if (up>0)
            ZZAuxFractal[n] = up;

         if (dn>0)
            ZZAuxFractal[n] = dn;
            
         if ((up == 0) && (dn == 0))
            ZZAuxFractal[n] = -1;
         n++;
      }
      i++;
      if (i > 3000) bSalida = true;
   }
}

bool FindZigZagInMICRO(ENUM_TIMEFRAMES tfBase,
                        double priceTarget,
                        datetime tFractalTF,   // tiempo de la barra del Periodo 
                        ENUM_TIMEFRAMES tfMicro,
                        datetime &t_Micro)
{
   int     tfm    = ConversorTF(tfMicro);
   int     tfb    = ConversorTF(tfBase);
   datetime tBeg  = tFractalTF;                        // inicio barra 
   datetime tEnd  = tFractalTF + PeriodSeconds(tfb);   // fin barra 
   t_Micro = 0;
   
   // empezamos en la barra M1 más cercana a tEnd-1 (para incluir todo el tramo)
   int shift = iBarShift(Par, tfm, tEnd, true);
   if(shift < 0) return false;

   for(int s = shift; s < iBars(Par, tfm); s++)
   {
      datetime tt = iTime(Par, tfm, s);
      if(tt < tBeg) break;                // ya salimos por el principio de la ventana
      if(tt >= tEnd) continue;            // estamos por delante; retrocede

      double zz = iCustom(Par, tfm, "ZigZag", MV32_Depth, Deviation, Backstep, 0, s);
      // Verificamos igualdad por precio entre
      //Zigzag PeriodoMiCRO con el valor del Fractal del PeriodoFractal
            
      if ((zz != 0.0) && NormalizeDouble(zz, Digitos) == NormalizeDouble(priceTarget, Digitos))
      {
         t_Micro = tt;

         // Verificamos igualdad por precio entre
         //fractal del PeriodoMiCRO con el valor del Fractal del PeriodoMICRO.
         double fUp = iFractals(Par, tfm, MODE_UPPER, s);
         double fDn = iFractals(Par, tfm, MODE_LOWER, s);
         
         if ((NormalizeDouble(fUp, Digitos) == NormalizeDouble(priceTarget, Digitos)) 
         || (NormalizeDouble(fDn, Digitos) == NormalizeDouble(priceTarget, Digitos)))
         {
            return true;
         }         
      }
   }
   
   return false;
}


bool PatronImpulsoOnda3M32(double dFractal, double &sl, int &direccion)
{
   //Patron basado en buscar en PeriodoMICRO, Ondas 2 u Ondas 3 consecutivas, en impulso, a 
   //partir del precio del fractal encontrado entre PeriodoFractal y PeriodoMICRO.
   bool bPatronOnda3M32 = false;
   sl = 0;
  
   //Leyendo las ultima posición del periodo MICRO
   ZigZagFractal(Par, PERIOD_M1, MV32_Depth, 3);
   // justo después de ZigZag(Par, PeriodoMICRO, MV32, 4);
   if(ZZAux[0] == 0.0 || ZZAux[1] == 0.0 || ZZAux[2] == 0.0) return false;
   
   Traza2 = "";
   Trazas(" PatronImpulsoOnda3M32: " + DoubleToStr(dFractal), Traza2);
   Trazas(" R0: " + DoubleToStr(ZZAux[0], Digitos) + " R1: " + DoubleToStr(ZZAux[1], Digitos) + " R2: " + DoubleToStr(ZZAux[2], Digitos), Traza2);

   if ((ZZAux[2] == dFractal) && (ZZAux[0] < ZZAux[1]) && (ZZAux[0] > ZZAux[2]) 
   && (ZZAux[1] > ZZAux[2]))
   {
      //ONDA 2
      Trazas(" PatronImpulsoOnda3M32: ONDA 2 Largos confirmada", Traza2);
      direccion = DIR_LARGOS;
   }
   else if ((ZZAux[2] == dFractal) && (ZZAux[0] > ZZAux[1]) && (ZZAux[0] < ZZAux[2]) 
   && (ZZAux[1] < ZZAux[2]))
   {
      Trazas(" PatronImpulsoOnda3M32: ONDA 2 Cortos confirmada", Traza2);   
      direccion = DIR_CORTOS;                
   }
   else
   {
      return false;
   }

   
   double ArrayPrecioMICRO[];
   int n1 = ArrayCopy(ArrayPrecioMICRO, ZZAux);
   
   double ArrayFractalMICRO[];
   int n2 = ArrayCopy(ArrayFractalMICRO, ZZAuxFractal);
   
   // (opcional) validar
   if(n1 <= 0)
   { 
      Trazas(" PatronImpulsoOnda3M32: ArrayCopy PrecioMICRO fallo: 0 elems", Traza2); 
      return false;
   }
   if(n2 <= 0)
   {
      Trazas(" PatronImpulsoOnda3M32: ArrayCopy FractalMICRO fallo: 0 elems", Traza2); 
      return false;
   }
   
   // 4) Ahora puedes recalcular MESO sin perder el MICRO clonado
   ZigZagFractal(Par, PERIOD_M5, MV8_Depth, 3);
   
   if ((ArraysEqualDoubles(ArrayFractalMICRO, ZZAuxFractal, Digitos, 0)) && (ArraysEqualDoubles(ArrayPrecioMICRO, ZZAux, Digitos, 0)))
   {
      //MICRO y MESO iguales en Zigzag y Fractales
      ZigZagFractal(Par, PERIOD_M5, MV32_Depth, 1);
      double ZZR0M532 = ZZAux[0];
      ZigZagFractal(Par, PERIOD_M15, MV8_Depth, 1);
      double ZZV0M158 = ZZAux[0];
   
      if ((dFractal == ZZV0M158) && (ZZV0M158 == ZZR0M532))
      {
         Trazas(" PatronImpulsoOnda3M32: Patron CONFIRMADO", Traza2);                 
         bPatronOnda3M32 = true;
         sl = ArrayPrecioMICRO[0];
      }
      else
      {
         Trazas(" PatronImpulsoOnda3M32: Patron SIN confirmar", Traza2);  
         return false;       
      }
   }
   else
   {
      Trazas(" PatronImpulsoOnda3M32: NO coincidencia Fractal-ZZ entre MICRO y MESO", Traza2); 
      return false;
   }   
   
   
   return(bPatronOnda3M32);
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


//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//                      FUNCIONES AUXILIARES

//--------------------------------------------------------------
// Punto gordo en Ask o Bid en el instante actual (vela M1 en curso)
// - side: 0 = ASK, 1 = BID
// - c   : color del punto
// - width: grosor del punto (5-7 queda muy gordo)
// - arrowcode: 159 = bullet Wingdings (punto sólido)
// Uso típico: PlotBigPointM1(0);  // ASK azul gordo ahora
//--------------------------------------------------------------
void PlotBigPointM1(int side = 0, color c = clrDodgerBlue, int width = 6, int arrowcode = 159)
{
   double price = (side == 0 ? Ask : Bid);
   price = NormalizeDouble(price, Digits);

   datetime tnow = TimeCurrent();  // instante actual (dentro de la vela M1 en curso)
   // Nombre único por símbolo+timestamp+tickcount para evitar colisiones
   string name = StringFormat("BigDot_%s_%d_%u", Symbol(), (int)tnow, GetTickCount());

   if(!ObjectCreate(0, name, OBJ_ARROW, 0, tnow, price))
   {
      Print("ObjectCreate falló: ", GetLastError());
      return;
   }

   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, arrowcode); // 159 = ● (Wingdings)
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);    // delante de las velas
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, false);
   // Opcional: bloquear para no arrastrar sin querer
   ObjectSetInteger(0, name, OBJPROP_READONLY, true);
}

ENUM_TIMEFRAMES GetCurrentPeriod()
{
   return (ENUM_TIMEFRAMES)Period();
}

void Reset()
{
   NotificacionEnviada = false;
   ActivadoPatronImpulsoOnda3M32 = false; 
   PintadoPrecio = false;                    
}

void Trazas(string cadena, string &Textofinal)
{
   string cadenafinal = "\n" + NowHMSStr() + cadena;
   Textofinal = Textofinal + cadenafinal;
}

string NowHMSStr()
{
   return TimeToString(TimeCurrent(), TIME_SECONDS); // "YYYY.MM.DD HH:MM:SS"
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

// Compara dos arrays double[] elemento a elemento.
// - digits: nº de decimales del símbolo (para NormalizeDouble)
// - eps: tolerancia absoluta opcional (por ej., 0.0001). Si eps>0, se usa MathAbs diff<=eps.
// Devuelve true si todos coinciden; false si tamaño distinto o algún valor no coincide.
bool ArraysEqualDoubles(const double &a[], const double &b[], int digits, double eps=0.0)
{
   int na = ArraySize(a);
   int nb = ArraySize(b);
   if(na != nb || na <= 0) return false;

   for(int i=0; i<na; i++)
   {
      double va = a[i];
      double vb = b[i];
      
      if (va == -1) return false;
      if (vb == -1) return false;

      if(eps > 0.0)
      {
         if(MathAbs(va - vb) > eps) return false;
      }
      else
      {
         if(NormalizeDouble(va, digits) != NormalizeDouble(vb, digits)) return false;
      }
   }
   return true;
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

// Pinta N días hacia atrás usando las velas D1
void DrawDailySeparators(int days_back)
{
   if(!PintarSeparadoresDia) return;

   for(int i=0; i<days_back; i++)
   {
      datetime dOpen = iTime(Par, PERIOD_D1, i);
      if(dOpen <= 0) break;
      DrawDaySeparator(dOpen);
   }
}

// Asegura que el separador del día (hoy) existe
void EnsureTodaySeparator()
{
   if(!PintarSeparadoresDia) return;

   datetime todayOpen = iTime(Par, PERIOD_D1, 0);
   if(todayOpen > 0)
      DrawDaySeparator(todayOpen);
}

void DrawDaySeparator(datetime dayOpen)
{
   string name = StringFormat("DaySep_%s_%s", Par, TimeToString(dayOpen, TIME_DATE));
   if(ObjectFind(0, name) >= 0) return;

   ObjectCreate(0, name, OBJ_VLINE, 0, dayOpen, 0);
   ObjectSetInteger(0, name, OBJPROP_COLOR, ColorSeparadorDia);
   ObjectSetInteger(0, name, OBJPROP_STYLE, EstiloSeparadorDia);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, AnchoSeparadorDia);
}
