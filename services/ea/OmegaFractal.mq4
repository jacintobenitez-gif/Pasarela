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

input bool  PintarHistorico = true;
input int   NumeroFractalesPintarHistorico = 40;
input bool  PintarLineaVertical = true;
input bool  Ejecutar_Operaciones = true; 
input bool  Backtesting = true; 
input bool  PintarSeparadoresDia   = true;
input int   DiasSeparadoresHist    = 4;           // cuántos días hacia atrás
input color ColorSeparadorDia      = clrDimGray;
input int   EstiloSeparadorDia     = STYLE_DOT;
input int   AnchoSeparadorDia      = 3;

//Variables Globales
int MV32_Depth = 32;
int MV8_Depth = 8;
int Deviation = 5;
int Backstep = 3;
string Par = Symbol();
int Digitos = (int)MarketInfo(Par, MODE_DIGITS);
bool PintarUnaVez = false;
double FractalLeido = 0;
double FractalActual = 0;
bool FractalValido = false;
bool LecturaMercado = true;
bool EntradaMercado = false;
bool SalidaMercado = false;
bool Trazas = false;
datetime t_PeriodoFractal;
double StopLoss = 0;

//ZigZag
double   ZZAux[];
datetime ZZAuxTime[];
datetime ZZAuxtMicro[1];

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
bool ConfirmacionFractalesMICROyMESOalineados = false;

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
      GetLastFractalsHistory(NumeroFractalesPintarHistorico);
      PintarUnaVez = true;
   }
   
   if(PintarSeparadoresDia)
      DrawDailySeparators(DiasSeparadoresHist);
   
//---
   return(INIT_SUCCEEDED);
  }
//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
//---

   if(PintarSeparadoresDia)
      EnsureTodaySeparator();

   FractalLeido = GetLastFractalNow(PeriodoFractal, Direccion, t_PeriodoFractal);

   Traza1 = "\n" + NowHMSStr() + " Fractal Leido: " + DoubleToStr(FractalLeido, Digitos);
   
   if (LecturaMercado)
   {      
      if (FractalLeido != FractalActual)
      {
         //Encontramos nuevo fractal y pintamos linea correspondiente para ayuda visual
         //en la lectura.
         
         FractalActual = FractalLeido;
         Traza1 = Traza1 + "\n" + NowHMSStr() + " Fractal Actual: " + DoubleToStr(FractalActual, Digitos);

         FractalValido = false;
         Traza1 = Traza1 + "\n" + NowHMSStr() + " PintarLineaVertical: " + DoubleToStr(PintarLineaVertical, Digitos);
         
         if (PintarLineaVertical)
         { 
            if (GetFractalinMICRO(FractalActual, FractalValido, t_PeriodoFractal))
            {
               Traza1 = Traza1 + "\n" + NowHMSStr() + " FractalinMicro: True"; 
               Traza1 = Traza1 + "\n" + NowHMSStr() + " Fractal Valido: " + DoubleToStr(FractalValido, Digitos);     
            }
            else
            {
               Traza1 = Traza1 + "\n" + NowHMSStr() + " FractalinMICRO: False";                  
            }
         } 
      }
      else if ((FractalLeido == FractalActual) && (FractalValido))
      {
         //Con el nuevo fractal, valido, procedo a buscar nuevas oportunidades de negocio.  
         Traza1 = "\n" + NowHMSStr() + " Fractal Leido - Actual: " + DoubleToStr(FractalActual, Digitos);
         
         //Busqueda de oportunidad de negocio: PatronImpulsoOnda3M32
         if (PatronImpulsoOnda3M32(FractalActual, Direccion, StopLoss))
         {
            ActivadoPatronImpulsoOnda3M32 = true; 
            Traza1 = Traza1 + "\n" + NowHMSStr() + " PatronImpulsoOnda3M32: True ";            
            Traza1 = Traza1 + "\n" + NowHMSStr() + " Status Ejecutar_Operaciones: " + IntegerToString(Ejecutar_Operaciones);            

            if (Ejecutar_Operaciones)
            {
               LecturaMercado = false;
               EntradaMercado = true;
               SalidaMercado = false;
            }           
         }      
      }
      
      Comment(Traza1);
   }
   else if (EntradaMercado)
   {      
      Traza1 = Traza1 + "\n" + NowHMSStr() + " EntradaMercado: True ";                        

      if (ActivadoPatronImpulsoOnda3M32) 
      { 
         //Reset
         ConfirmacionFractalesMICROyMESOalineados = false;     
         Traza1 = Traza1 + "\n" + NowHMSStr() + " Patron encontrado: PatronImpulsoOnda3M32 "; 
         
         double Lote = 0;
         
         if (Backtesting)
         {
            Lote = MarketInfo(Par, MODE_MINLOT);      
         }
         else
         {
            Lote = 0.1;
         }                       
         
         int OperacionesEjecutadas = ExecMarket(Direccion, 1, StopLoss, Lote, Par + "-P1");
         
         //Ejecutas orden en el mercado
         if  (OperacionesEjecutadas > 0)
         {
            Traza1 = Traza1 + "\n" + NowHMSStr() + " OperacionesEjecutadas: " + IntegerToString(OperacionesEjecutadas);                        
            LecturaMercado = false;
            EntradaMercado = false;
            SalidaMercado = true;
         }
      }

      Comment(Traza1);
      
   }
   else if (SalidaMercado)
   {
      //Verificar que todas las operaciones se cerraron
      //damos paso a la lectura del mercado
      Traza1 =  Traza1 + "\n" + NowHMSStr() + " SalidaMercado True: ";                        
      
      if (ActivadoPatronImpulsoOnda3M32)
      {
         //La salida puede ser por:
         // SL: Salida controlado por el sistema. Tengo que verificar que se cerraron las operaciones abiertas.
         // SalidaPatronImpulsoOnda3M32: Salida controlada por mi.         
         string commentSalida = Par + "-P1";

         //Salida: SL
         if (CountOpenOrdersByComment(commentSalida) == 0)
         {
            Traza1 = Traza1 + "\n" + NowHMSStr() + " Salida SL: Operacion cerradas por StopLoss ";                        
            ActivadoPatronImpulsoOnda3M32 = false;
            LecturaMercado = true;
            EntradaMercado = false;
            SalidaMercado = false;                           
         }
         
         //Salida PatronImpulsoOnda3M32: Cerrar ordenes mercado controlado por mi.
         if (SalidaPatronImpulsoOnda3M32(FractalActual, Direccion))  
         {
            // Cierre por TP lógico (condición de salida)
            int cerradas = CierreOrdenes(commentSalida);
   
            // Reset de estado si ya no quedan órdenes con ese comentario
            if (cerradas > 0)
            {
               Traza1 = Traza1 + "\n" + NowHMSStr() + " SalidaPatronImpulsoOnda3M32: " + IntegerToString(cerradas);                        

               ActivadoPatronImpulsoOnda3M32 = false;
               LecturaMercado = true;
               EntradaMercado = false;
               SalidaMercado = false;               
            }
         } 
      }

      Comment(Traza1);
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
   ZigZag(Par, PeriodoMICRO, MV32_Depth, 4);
   // justo después de ZigZag(Par, PeriodoMICRO, MV32, 4);
   if(ZZAux[0] == 0.0 || ZZAux[1] == 0.0 || ZZAux[2] == 0.0) return false;
   
   Traza1 = Traza1 + "\nPatronImpulsoOnda3M32";
   
   if (dir == DIR_LARGOS)
   {
      Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: LARGOS";

      if ((ZZAux[2] == dFractal) && (ZZAux[0] < ZZAux[1]) 
      && (ZZAux[1] > ZZAux[2]))
      {
         double ZZR2 = ZZAux[2];
         double ZZR1 = ZZAux[1];
         double ZZR0 = ZZAux[0];

         //Leyendo las ultima posición del PeriodoMESO
         //para comparar las con las ondas M32 del PeriodoMICRO
         ZigZag(Par, PeriodoMESO, MV8_Depth, 3);
         if(ZZAux[0] == 0.0 || ZZAux[1] == 0.0 || ZZAux[2] == 0.0) return false;
         
         if ((ZZR0 == ZZAux[0]) && (ZZR1 == ZZAux[1]) && (ZZR2 == ZZAux[2]))
         {
            Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Detectada ONDA2";

            //ONDA 2
            datetime t_Meso = 0;
            datetime t_Micro = 0;
            int DireccionMeso = 0;
            
            double FractalMeso = GetLastFractalNow(PeriodoMESO, DireccionMeso, t_Meso);
 
            if (!ConfirmacionFractalesMICROyMESOalineados)
            {
               if (FindZigZagInWindow(PeriodoMESO, FractalMeso, t_Meso, PeriodoMICRO, t_Micro))
               {
                  Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Fractales MICRO y MESO SI alineados";
                  ConfirmacionFractalesMICROyMESOalineados = true;
                  ZZAuxtMicro[0] = t_Micro;                  
               } 
               else
               {
                  Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Fractales MICRO y MESO NO alineados";               
               } 
            }
                  
            if ((ConfirmacionFractalesMICROyMESOalineados) 
            && ((DirEMA1vsEMA5(PeriodoMICRO, dir)) && (DirEMA1vsEMA5(PeriodoMESO, dir))))
            {
               Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Patrón confirmado";        
               //Trigger Operacion Largos
               bPatronOnda3M32 = true;
               sl = ZZR0;
               Traza1 = Traza1 + "\nDrawOmega - Parametros entrada:";        
               Traza1 = Traza1 + "\n t_Micro: " + StringFormat("%s", TimeToString(t_Micro, TIME_DATE|TIME_SECONDS)) + " ZZR0: " + DoubleToStr(ZZR0);
               DrawOmega(ZZAuxtMicro[0], ZZR0, 10, clrGold, 20);               
            } 
            else
            {
               Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Direccion MICRO y MESO: No alineadas";        
               return false;
            }                    
         }         
      }
   }
   else if (dir == DIR_CORTOS)
   {
      Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: CORTOS";

      if ((ZZAux[2] == dFractal) && (ZZAux[0] > ZZAux[1]) 
      && (ZZAux[1] < ZZAux[2]))
      {
         double ZZR2 = ZZAux[2];
         double ZZR1 = ZZAux[1];
         double ZZR0 = ZZAux[0];

         //Leyendo las ultima posición del PeriodoMESO
         //para comparar las con las ondas M32 del PeriodoMICRO
         ZigZag(Par, PeriodoMESO, MV8_Depth, 3);
         if(ZZAux[0]==0.0 || ZZAux[1]==0.0 || ZZAux[2]==0.0) return false;
         
         if ((ZZR0 == ZZAux[0]) && (ZZR1 == ZZAux[1]) && (ZZR2 == ZZAux[2]))
         {
            Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Detectada ONDA2";

            //ONDA 2
            datetime t_Meso = 0;
            datetime t_Micro = 0;
            int DireccionMeso = 0;
            
            double FractalMeso = GetLastFractalNow(PeriodoMESO, DireccionMeso, t_Meso);

            if (!ConfirmacionFractalesMICROyMESOalineados)
            {
               if (FindZigZagInWindow(PeriodoMESO, FractalMeso, t_Meso, PeriodoMICRO, t_Micro))
               {
                  Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Fractales MICRO y MESO SI alineados";
                  ConfirmacionFractalesMICROyMESOalineados = true;
                  ZZAuxtMicro[0] = t_Micro;                                    
               } 
               else
               {
                  Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Fractales MICRO y MESO NO alineados";               
               } 
            }
                        
            if ((ConfirmacionFractalesMICROyMESOalineados) 
            && ((DirEMA1vsEMA5(PeriodoMICRO, dir)) && (DirEMA1vsEMA5(PeriodoMESO, dir))))
            {
               Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Patrón confirmado";        
               //Trigger Operacion Largos
               bPatronOnda3M32 = true;
               sl = ZZR0;
               Traza1 = Traza1 + "\nDrawOmega - Parametros entrada:";        
               Traza1 = Traza1 + "\n t_Micro: " + StringFormat("%s", TimeToString(t_Micro, TIME_DATE|TIME_SECONDS)) + " ZZR0: " + DoubleToStr(ZZR0);
               DrawOmega(ZZAuxtMicro[0], ZZR0, 10, clrGold, 20);
            } 
            else
            {
               Traza1 = Traza1 + "\nPatronImpulsoOnda3M32: Direccion MICRO y MESO: No alineadas";        
               return false;
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
   ZigZag(Par, PeriodoMICRO, MV32_Depth, 4);
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

//+------------------------------------------------------------------+
double GetLastFractalNow(ENUM_TIMEFRAMES Periodoaleer, int &DireccionActual, datetime &t_TimeFractal)
{
   int dir = DIR_NODIR;
   int contador = 0;
   int lookback = 1;
   double Fractal = 0;

   // Recorremos barras desde la más reciente (shift=0) hacia atrás
   int tfconvertido = ConversorTF(Periodoaleer);
   int total = iBars(Par, tfconvertido);         
   for (int i = 0; i < total; i++)
   {
      double up  = iFractals(Par, tfconvertido, MODE_UPPER, i);
      double dn  = iFractals(Par, tfconvertido, MODE_LOWER, i);
      
      if (up > 0)
      {
         Fractal = up;
         t_TimeFractal = iTime(Par, tfconvertido, i);           
         DireccionActual = DIR_CORTOS;
         contador++;          
      }
      else if (dn > 0)
      {
         Fractal = dn;
         t_TimeFractal = iTime(Par, tfconvertido, i);           
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
         datetime t_Fractal = iTime(Par, tfconvertido, i); 
          
         if (PintarLineaVertical) 
            GetFractalinMICRO(Fractal, dummy, t_Fractal);  
         contador++;          
      }
      else if (dn > 0)
      {
         Fractal = dn;
         bool dummy=false;
         datetime t_Fractal = iTime(Par, tfconvertido, i);  
         
         if (PintarLineaVertical) 
            GetFractalinMICRO(Fractal, dummy, t_Fractal);
         contador++;
      }      
      
      if (contador >= lookback)
         break;
      
   }   
}

bool GetFractalinMICRO(double Price, bool &FValido, datetime tPeriodoFractal)
{
   // Recorremos barras desde la más reciente (shift=0) hacia atrás
   int tfconvertido = ConversorTF(PeriodoMICRO);   
   int total = iBars(Par, tfconvertido);     
   FValido = false;
   bool bEncontrado = false;
 
   for (int i = 0; i < total; i++)
   {
      double up  = iFractals(Par, tfconvertido, MODE_UPPER, i);
      double dn  = iFractals(Par, tfconvertido, MODE_LOWER, i);
        
      if (NormalizeDouble(up, Digitos) == NormalizeDouble(Price, Digitos))
      {  
         datetime t_m1 = 0;
               
         if (FindZigZagInWindow(PeriodoFractal, Price, tPeriodoFractal, PeriodoMICRO, t_m1)) 
         {
            DrawVLine(t_m1, clrRed);
            FValido = true;
            bEncontrado = true;
         }
         else
         {
            DrawVLine(t_m1, clrOrange);
            FValido = false;
            bEncontrado = true;
         }
         
         break;      
      }
      else if (NormalizeDouble(dn, Digitos) == NormalizeDouble(Price, Digitos))
      {
         datetime t_m1 = 0;

         if (FindZigZagInWindow(PeriodoFractal, Price, tPeriodoFractal, PeriodoMICRO, t_m1)) 
         {
            DrawVLine(t_m1, clrGreen);
            FValido = true; 
            bEncontrado = true;                       
         }           
         else
         {
            DrawVLine(t_m1, clrOrange);
            FValido = false;
            bEncontrado = true;            
         }
            
         break;
      }
   }
   
   return(bEncontrado);
   
}

bool FindZigZagInWindow(ENUM_TIMEFRAMES tfBase,
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
      zig = iCustom(sMarket, iPeriodo, "ZigZag", ZZPeriodo, Deviation, Backstep, 0, i);
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
   color  clr        = clrWhite;

   Traza1 = Traza1 + "\nDireccion: " + IntegerToString(dir) + " Operaciones maximas: " + IntegerToString(maxOps);
   Traza1 = Traza1 + "\nSL: " + DoubleToString(sl) + " Lotes: " + DoubleToString(lots) + " Comentario: " + comment;
   
   double Lote_minimo = MarketInfo(Par, MODE_MINLOT);
   double Lote_maximo = MarketInfo(Par, MODE_MAXLOT);
   
   if ((lots >= Lote_minimo) && (lots <= Lote_maximo))
   {
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
            clr   = clrRed;
         }
         else // DIR_CORTOS
         {
            type  = OP_SELL;
            price = NormalizeDouble(Bid, Digitos);
            tp    = 0.0;
            clr   = clrGreen;
         }
   
         // Enviar orden
         int ticket = OrderSend(Par, type, lots, price, slippage, sl_price, tp, comment, magic, 0, clr);
         if(ticket < 0)
         {
            // Si falla, intentamos seguir con el resto (por si es un fallo puntual)
            // Puedes loguear el error:
            Traza1 = Traza1 + "\nOrderSend: " + IntegerToString(GetLastError());
         }
         else
         {
            Traza1 = Traza1 + "\nTicket: " + IntegerToString(ticket);         
            opened++;
         }
      }
   
      Traza1 = Traza1 + "\nOperaciones Abiertas: " + IntegerToString(opened);         
   
   }
   else
   {
      Traza1 = Traza1 + "\nActualizar Lote actual: " + DoubleToStr(lots, Digitos) + " Lote minimo: " + DoubleToStr(Lote_minimo) + " Lote maximo: " + DoubleToStr(Lote_maximo);               
   }
     
   return (opened);
   
}

// Cuenta cuántas órdenes ABIERTAS hay con un comentario EXACTO (y del símbolo actual)
int CountOpenOrdersByComment(string targetComment)
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

void DrawDaySeparator(datetime dayOpen)
{
   string name = StringFormat("DaySep_%s_%s", Par, TimeToString(dayOpen, TIME_DATE));
   if(ObjectFind(0, name) >= 0) return;

   ObjectCreate(0, name, OBJ_VLINE, 0, dayOpen, 0);
   ObjectSetInteger(0, name, OBJPROP_COLOR, ColorSeparadorDia);
   ObjectSetInteger(0, name, OBJPROP_STYLE, EstiloSeparadorDia);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, AnchoSeparadorDia);
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

string NowHMSStr()
{
   return TimeToString(TimeCurrent(), TIME_SECONDS); // "YYYY.MM.DD HH:MM:SS"
}

void DrawOmega(datetime t, double price, int offsetPoints=50, color col=clrGold, int fontSize=32)
{

   double p    = NormalizeDouble(price - offsetPoints*Point, Digitos);

   string base = StringFormat("OMEGA_%s_%d", Par, (int)t);
   string name = base; static int seq=0;
   while(ObjectFind(0, name) >= 0) { seq++; name = StringFormat("%s_%d", base, seq); }

   ObjectCreate(0, name, OBJ_TEXT, 0, t, p);
   ObjectSetText(name, "Ω", fontSize, "Arial", col);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}



//------------------------BORRAR A FUTURO-------------------------